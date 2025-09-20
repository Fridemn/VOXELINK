"""
声纹识别服务 - 提供声纹识别功能
"""

import os
import uuid
import sqlite3
import logging
import numpy as np
import base64
from typing import Dict, Any, List, Tuple, Optional, Union, Callable

from ..core.stt_config import get_settings

# 配置日志
logger = logging.getLogger("vpr_service")


class VPRService:
    """声纹识别服务类"""
    
    def __init__(self):
        """初始化声纹识别服务"""
        self.settings = get_settings()
        self.database_dir = self.settings.get("database_dir", "./database")
        os.makedirs(self.database_dir, exist_ok=True)  # 确保数据库目录存在
        self.db_path = os.path.join(self.database_dir, "voiceprint.db")
        self.vpr_model = self.settings.get(
            "vpr_model", "./model_cache/models/damo/speech_eres2netv2_sv_zh-cn_16k-common"
        )
        self.similarity_threshold = self.settings.get("vpr_similarity_threshold", 0.25)
        self.vpr_debug = self.settings.get("vpr_debug", False)

        # 添加缓存设置
        self.use_cache = self.settings.get("use_cache", True)
        self.cache_size = self.settings.get("cache_size", 100)  # 最多缓存的embedding数量
        self.embeddings_cache = {}  # 用户ID -> embedding的缓存
        self.cache_hits = 0
        self.cache_misses = 0

        # 初始化声纹识别模型
        self._init_model()

        # 初始化SQLite数据库
        self._init_database()

        # 如果启用缓存，预加载声纹
        if self.use_cache:
            self._preload_embeddings()

        # 回调函数
        self.on_registration_callback = None
    
    def _init_model(self):
        """初始化声纹识别模型"""
        try:
            from modelscope.pipelines import pipeline
            
            logger.info(f"正在加载声纹识别模型: {self.vpr_model}")
            self.sv_pipeline = pipeline(
                task="speaker-verification",
                model=self.vpr_model,
            )
            logger.info("声纹识别模型加载完成")
            
        except Exception as e:
            logger.error(f"初始化声纹识别模型失败: {str(e)}", exc_info=True)
            self.sv_pipeline = None
    
    def _init_database(self):
        """初始化SQLite数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 创建声纹表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS voiceprints (
            id TEXT PRIMARY KEY,
            person_name TEXT,
            embedding BLOB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # 添加索引以加速查询
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_person_name ON voiceprints(person_name)')

        conn.commit()
        conn.close()

        logger.info(f"声纹数据库初始化完成: {self.db_path}")

    def _preload_embeddings(self):
        """预加载声纹嵌入到缓存"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 获取最近添加的声纹（限制数量）
            cursor.execute("""
                SELECT id, embedding FROM voiceprints
                ORDER BY created_at DESC
                LIMIT ?
            """, (self.cache_size,))

            rows = cursor.fetchall()
            conn.close()

            # 清空当前缓存
            self.embeddings_cache.clear()

            # 加载到缓存
            for row in rows:
                _id, embedding_binary = row
                embedding = np.frombuffer(embedding_binary, dtype=np.float32)
                self.embeddings_cache[_id] = embedding

            logger.info(f"预加载了{len(self.embeddings_cache)}个声纹到缓存")

        except Exception as e:
            logger.error(f"预加载声纹缓存失败: {str(e)}", exc_info=True)

    def _update_cache(self, user_id, embedding):
        """更新声纹缓存"""
        if not self.use_cache:
            return

        # 如果缓存已满，移除最早的一项
        if len(self.embeddings_cache) >= self.cache_size:
            # 简单的LRU策略：移除第一个键
            oldest_key = next(iter(self.embeddings_cache))
            del self.embeddings_cache[oldest_key]

        # 添加到缓存
        self.embeddings_cache[user_id] = embedding

    def _get_cached_embedding(self, user_id):
        """从缓存获取声纹embedding"""
        if not self.use_cache:
            return None

        embedding = self.embeddings_cache.get(user_id)
        if embedding is not None:
            self.cache_hits += 1
        else:
            self.cache_misses += 1

        return embedding

    def register_voiceprint(self, user_id: str, user_name: str, audio_data: bytes) -> Dict[str, Any]:
        """注册声纹
        
        Args:
            user_id: 用户ID
            user_name: 用户名称
            audio_data: 音频数据
            
        Returns:
            注册结果
        """
        if self.sv_pipeline is None:
            return {"success": False, "error": "声纹识别模型未初始化"}
        
        try:
            # 转换数据格式
            frames = [np.frombuffer(audio_data, dtype=np.int16)]
            
            # 检查数据是否有效
            if len(frames[0]) == 0:
                return {"success": False, "error": "音频数据无效"}
            
            # 连接数据库
            conn = sqlite3.connect(self.db_path)
            
            # 检查是否已存在
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM voiceprints WHERE id = ?", (user_id,))
            exists = cursor.fetchone()
            
            if exists:
                # 删除已存在的记录
                cursor.execute("DELETE FROM voiceprints WHERE id = ?", (user_id,))
            
            # 提取音频的声纹特征
            audio_data_np = np.concatenate(frames, axis=0)
            result = self.sv_pipeline([audio_data_np], output_emb=True)
            embedding = result["embs"][0]
            
            # 将embedding转换为二进制数据
            embedding_binary = embedding.tobytes()
            
            # 保存到数据库
            cursor.execute(
                "INSERT INTO voiceprints (id, person_name, embedding) VALUES (?, ?, ?)",
                (user_id, user_name, embedding_binary)
            )
            conn.commit()
            conn.close()
            
            # 更新缓存
            self._update_cache(user_id, embedding)
            
            logger.info(f"声纹注册成功 - ID: {user_id}, 用户名: {user_name}")
            
            # 触发回调
            if self.on_registration_callback:
                self.on_registration_callback(user_id, user_name)
                
            return {
                "success": True, 
                "message": "声纹注册成功",
                "user_id": user_id,
                "user_name": user_name
            }
        except Exception as e:
            logger.error(f"声纹注册失败: {str(e)}", exc_info=True)
            return {"success": False, "error": f"声纹注册失败: {str(e)}"}
    
    def remove_voiceprint(self, user_id: str) -> Dict[str, Any]:
        """删除声纹
        
        Args:
            user_id: 用户ID
            
        Returns:
            删除结果
        """
        try:
            if not user_id:
                return {"success": False, "error": "缺少用户ID"}
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 先检查是否存在
            cursor.execute("SELECT id FROM voiceprints WHERE id = ?", (user_id,))
            exists = cursor.fetchone()
            
            if not exists:
                return {"success": False, "error": f"未找到ID为 {user_id} 的声纹记录"}
            
            # 执行删除
            cursor.execute("DELETE FROM voiceprints WHERE id = ?", (user_id,))
            conn.commit()
            conn.close()
            
            # 清理缓存
            if user_id in self.embeddings_cache:
                del self.embeddings_cache[user_id]
                
            message = f"成功删除声纹ID: {user_id}"
            logger.info(message)
            
            return {"success": True, "message": message}
            
        except Exception as e:
            logger.error(f"删除声纹失败: {str(e)}", exc_info=True)
            return {"success": False, "error": f"删除声纹失败: {str(e)}"}
    
    def list_voiceprints(self) -> Dict[str, Any]:
        """获取声纹列表
        
        Returns:
            声纹列表
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 查询所有声纹记录
            cursor.execute("SELECT id, person_name FROM voiceprints")
            rows = cursor.fetchall()
            
            # 构建结果列表
            voiceprints = []
            for row in rows:
                voiceprints.append({
                    "user_id": row[0],
                    "user_name": row[1] or "未命名用户"
                })
                
            conn.close()
            
            logger.info(f"获取到 {len(voiceprints)} 条声纹记录")
            return {"success": True, "voiceprints": voiceprints}
            
        except Exception as e:
            logger.error(f"获取声纹列表失败: {str(e)}", exc_info=True)
            return {"success": False, "error": f"获取声纹列表失败: {str(e)}"}
    
    def identify_voiceprint(self, audio_data: bytes) -> Dict[str, Any]:
        """识别声纹
        
        Args:
            audio_data: 音频数据
            
        Returns:
            识别结果
        """
        if self.sv_pipeline is None:
            return {"success": False, "error": "声纹识别模型未初始化"}
        
        try:
            # 确保音频数据不为空
            if not audio_data or len(audio_data) == 0:
                logger.error("音频数据为空")
                return {"success": False, "error": "音频数据为空"}
                
            # 转换为数据格式
            frames = [np.frombuffer(audio_data, dtype=np.int16)]
            
            # 检查数据是否有效
            if len(frames[0]) == 0:
                return {"success": False, "error": "音频数据无效"}
            
            # 确保音频数据长度足够
            audio_data_np = np.concatenate(frames, axis=0)
            if len(audio_data_np) < 8000:  # 至少需要0.5秒的16kHz音频
                logger.warning(f"音频数据过短: {len(audio_data_np)} 样本, 可能影响识别质量")
                # 填充静音使其达到最小长度
                padding = np.zeros(max(8000 - len(audio_data_np), 0), dtype=audio_data_np.dtype)
                audio_data_np = np.concatenate([audio_data_np, padding])
            
            # 计算输入音频的声纹特征
            result = self.sv_pipeline([audio_data_np], output_emb=True)
            input_embedding = result["embs"][0]
            
            # 获取所有声纹
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id, person_name, embedding FROM voiceprints")
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                logger.warning("声纹库为空，无法进行匹配")
                return {"success": False, "error": "声纹库为空，无法进行匹配"}
            
            # 与声纹库中的所有声纹比对
            max_similarity = -1.0
            best_person_name = "Unknown"
            best_id = None
            
            for row in rows:
                _id, _person_name, embedding_binary = row
                
                # 尝试从缓存获取embedding
                stored_embedding = self._get_cached_embedding(_id)
                
                # 如果缓存未命中，从数据库加载
                if stored_embedding is None:
                    # 将二进制数据转换回numpy数组
                    stored_embedding = np.frombuffer(embedding_binary, dtype=np.float32).reshape(input_embedding.shape)
                    # 更新缓存
                    self._update_cache(_id, stored_embedding)
                
                # 计算余弦相似度
                similarity = float(self._compute_similarity(input_embedding, stored_embedding))
                
                if self.vpr_debug:
                    logger.debug(f"声纹匹配结果: {_person_name}, 相似度: {similarity:.4f}")
                
                if similarity > max_similarity:
                    max_similarity = float(similarity)
                    best_person_name = _person_name
                    best_id = _id
            
            # 判断是否超过阈值
            if max_similarity >= self.similarity_threshold:
                logger.info(f"声纹匹配成功: {best_person_name}, 相似度: {max_similarity:.4f}")
                return {
                    "success": True,
                    "user_id": best_id,
                    "user_name": best_person_name,
                    "similarity": float(max_similarity)
                }
            else:
                logger.info(f"声纹匹配失败，最高相似度: {max_similarity:.4f}，低于阈值: {self.similarity_threshold}")
                return {"success": False, "error": "声纹识别失败，无匹配结果"}
                
        except Exception as e:
            logger.error(f"声纹识别异常: {str(e)}", exc_info=True)
            return {"success": False, "error": f"声纹识别失败: {str(e)}"}
    
    def compare_voiceprints(self, audio_data1: bytes, audio_data2: bytes) -> Dict[str, Any]:
        """比对两段音频的声纹相似度
        
        Args:
            audio_data1: 第一段音频数据
            audio_data2: 第二段音频数据
            
        Returns:
            比对结果
        """
        if self.sv_pipeline is None:
            return {"success": False, "error": "声纹识别模型未初始化"}
        
        try:
            # 转换为数据格式
            frames1 = [np.frombuffer(audio_data1, dtype=np.int16)]
            frames2 = [np.frombuffer(audio_data2, dtype=np.int16)]
            
            # 检查数据是否有效
            if len(frames1[0]) == 0 or len(frames2[0]) == 0:
                return {"success": False, "error": "音频数据无效"}
            
            # 提取声纹特征
            audio_data1_np = np.concatenate(frames1, axis=0)
            audio_data2_np = np.concatenate(frames2, axis=0)
            
            result1 = self.sv_pipeline([audio_data1_np], output_emb=True)
            result2 = self.sv_pipeline([audio_data2_np], output_emb=True)
            
            embedding1 = result1["embs"][0]
            embedding2 = result2["embs"][0]
            
            # 计算相似度
            similarity = self._compute_similarity(embedding1, embedding2)
            
            # 判断是否为同一个人
            is_same_person = similarity >= self.similarity_threshold
            
            logger.info(f"声纹比对结果 - 相似度: {similarity:.4f}, 是否为同一人: {is_same_person}")
            
            return {
                "success": True,
                "similarity": float(similarity),
                "is_same_person": bool(is_same_person)
            }
        except Exception as e:
            logger.error(f"声纹比对异常: {str(e)}", exc_info=True)
            return {"success": False, "error": f"声纹比对失败: {str(e)}"}
    
    def _compute_similarity(self, embedding1, embedding2):
        """计算两个向量的余弦相似度

        Args:
            embedding1: 第一个向量
            embedding2: 第二个向量

        Returns:
            float: 余弦相似度
        """
        return float(np.dot(embedding1, embedding2) / (np.linalg.norm(embedding1) * np.linalg.norm(embedding2)))
    
    def decode_audio(self, base64_audio: str) -> Optional[bytes]:
        """解码Base64编码的音频数据

        Args:
            base64_audio: Base64编码的音频数据

        Returns:
            解码后的音频数据
        """
        try:
            return base64.b64decode(base64_audio)
        except Exception as e:
            logger.error(f"解码音频数据失败: {str(e)}")
            return None
    
    def register_callback(self, callback: Callable[[str, str], None]) -> None:
        """注册声纹注册成功的回调函数

        Args:
            callback: 回调函数，接收参数(user_id, person_name)
        """
        self.on_registration_callback = callback


# 全局单例
_vpr_service = None


def get_vpr_service() -> VPRService:
    """获取VPR服务实例

    Returns:
        VPR服务实例
    """
    global _vpr_service
    if _vpr_service is None:
        _vpr_service = VPRService()
    return _vpr_service
