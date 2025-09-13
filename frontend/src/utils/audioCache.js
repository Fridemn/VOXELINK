/**
 * 音频缓存管理器
 * 用于存储和管理已下载的音频文件，避免重复下载
 */
class AudioCache {
  constructor() {
    this.cache = new Map(); // URL -> Blob URL映射
  }

  /**
   * 添加音频到缓存
   * @param {string} url 原始URL
   * @param {string} blobUrl Blob URL
   */
  set(url, blobUrl) {
    this.cache.set(url, blobUrl);
  }

  /**
   * 从缓存获取音频Blob URL
   * @param {string} url 原始URL
   * @returns {string|null} Blob URL或null
   */
  get(url) {
    return this.cache.has(url) ? this.cache.get(url) : null;
  }

  /**
   * 检查URL是否在缓存中
   * @param {string} url 原始URL
   * @returns {boolean}
   */
  has(url) {
    return this.cache.has(url);
  }

  /**
   * 从缓存移除音频
   * @param {string} url 原始URL
   */
  remove(url) {
    if (this.cache.has(url)) {
      URL.revokeObjectURL(this.cache.get(url));
      this.cache.delete(url);
    }
  }

  /**
   * 清除所有缓存
   */
  clear() {
    this.cache.forEach((blobUrl) => {
      URL.revokeObjectURL(blobUrl);
    });
    this.cache.clear();
  }

  /**
   * 加载并缓存音频
   * @param {string} url 音频URL
   * @returns {Promise<string>} Blob URL
   */
  async loadAndCache(url) {
    if (this.has(url)) {
      return this.get(url);
    }

    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`音频加载失败: ${response.status}`);
      }

      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      this.set(url, blobUrl);
      return blobUrl;
    } catch (error) {
      console.error('加载音频失败:', error);
      return null;
    }
  }
}

// 创建单例
const audioCache = new AudioCache();
export default audioCache;
