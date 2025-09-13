import request from '@/api/request'
import { addCancelToken } from '@/api/request/cancel'

/**
 * 聊天接口
 * @param {Object} data - 聊天请求数据
 * @param {string} [data.model] - 模型名称（可选）
 * @param {string} data.message - 消息内容
 * @param {string} [data.history_id] - 历史记录ID（可选）
 * @param {string} [data.role='user'] - 消息角色（默认为'user'）
 * @returns {object} 包含请求promise和取消令牌的对象
 */
export const chat = (data) => {
  const config = {
    headers: {
      'Content-Type': 'application/json'
    }
  }
  const source = addCancelToken(config)
  
  return {
    request: request.post('/llm/chat', data, config),
    source
  }
}

/**
 * 流式聊天接口
 * @param {Object} data - 聊天请求数据
 * @param {string} [data.model] - 模型名称（可选）
 * @param {string} data.message - 消息内容
 * @param {string} [data.history_id] - 历史记录ID（可选）
 * @param {string} [data.role='user'] - 消息角色（默认为'user'）
 * @returns {object} 包含请求promise和取消令牌的对象
 */
export const chatStream = (data) => {
  // 注意：不要使用axios进行流式请求，直接使用fetch API
  const config = {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream'
    },
    body: JSON.stringify(data)
  }
  
  // 构建正确的URL（确保不会有重复的斜杠）
  const baseApi = import.meta.env.VITE_BASE_API || 'http://127.0.0.1:8000'
  const cleanBaseApi = baseApi.endsWith('/') ? baseApi.slice(0, -1) : baseApi
  const url = `${cleanBaseApi}/llm/chat/stream`
  
  // 创建AbortController
  const controller = new AbortController()
  config.signal = controller.signal
  
  return {
    request: fetch(url, config),
    controller
  }
}

/**
 * 创建新的历史记录
 * @returns {object} 包含请求promise和取消令牌的对象
 */
export const createNewHistory = () => {
  const config = {}
  const source = addCancelToken(config)
  
  return {
    request: request.post('/llm/history/new', null, config),
    source
  }
}

/**
 * 获取历史消息
 * @param {string} historyId - 历史记录ID
 * @returns {object} 包含请求promise和取消令牌的对象
 */
export const getHistory = (historyId) => {
  const config = {}
  const source = addCancelToken(config)
  
  return {
    request: request.get(`/llm/history/${historyId}`, config),
    source
  }
}

/**
 * 删除历史记录
 * @param {string} historyId - 历史记录ID
 * @returns {object} 包含请求promise和取消令牌的对象
 */
export const deleteHistory = (historyId) => {
  const config = {}
  const source = addCancelToken(config)
  
  return {
    request: request.delete(`/llm/history/${historyId}`, config),
    source
  }
}

/**
 * 更新历史记录标题
 * @param {string} historyId - 历史记录ID
 * @param {Object} data - 更新数据
 * @param {string} data.title - 新标题
 * @returns {object} 包含请求promise和取消令牌的对象
 */
export const updateHistoryTitle = (historyId, data) => {
  const config = {
    headers: {
      'Content-Type': 'application/json'
    }
  }
  const source = addCancelToken(config)
  
  return {
    request: request.put(`/llm/history/${historyId}`, data, config),
    source
  }
}

/**
 * 获取用户所有聊天历史
 * @returns {object} 包含请求promise和取消令牌的对象
 */
export const getUserHistories = () => {
  const config = {}
  const source = addCancelToken(config)
  
  return {
    request: request.get('/llm/user/histories', config),
    source
  }
}

/**
 * 自动总结历史记录内容并更新标题
 * @param {string} historyId - 历史记录ID
 * @returns {object} 包含请求promise和取消令牌的对象
 */
export const summarizeHistoryTitle = (historyId) => {
  const config = {}
  const source = addCancelToken(config)
  
  return {
    request: request.post(`/llm/history/${historyId}/summarize`, null, config),
    source
  }
}