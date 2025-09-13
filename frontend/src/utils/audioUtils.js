/**
 * 音频处理工具函数
 */

/**
 * 根据URL获取适当的音频MIME类型
 * @param {string} url 音频URL
 * @returns {string} MIME类型
 */
export const getAudioMimeType = (url) => {
  if (!url) return 'audio/mpeg';
  
  const lowerUrl = url.toLowerCase();
  if (lowerUrl.endsWith('.mp3')) return 'audio/mpeg';
  if (lowerUrl.endsWith('.wav')) return 'audio/wav';
  if (lowerUrl.endsWith('.ogg')) return 'audio/ogg';
  if (lowerUrl.endsWith('.m4a')) return 'audio/mp4';
  if (lowerUrl.endsWith('.aac')) return 'audio/aac';
  
  return 'audio/mpeg'; // 默认类型
};

/**
 * 创建本地音频Blob URL
 * @param {Blob} blob 音频Blob对象
 * @param {string} mimeType MIME类型
 * @returns {string} Blob URL
 */
export const createAudioBlobUrl = (blob, mimeType = 'audio/wav') => {
  // 确保有正确的MIME类型
  const typedBlob = new Blob([blob], { type: mimeType });
  return URL.createObjectURL(typedBlob);
};

/**
 * 尝试播放音频元素
 * @param {HTMLAudioElement} audioElement 音频元素
 * @returns {Promise<void>}
 */
export const playAudio = async (audioElement) => {
  if (!audioElement) return;
  
  try {
    await audioElement.play();
  } catch (error) {
    console.warn('无法自动播放音频:', error.message);
  }
};

/**
 * 设置音频元素的源
 * @param {HTMLAudioElement} audioElement 音频元素
 * @param {string} src 音频源URL
 * @param {string} type MIME类型
 */
export const setAudioSource = (audioElement, src, type) => {
  if (!audioElement) return;
  
  // 创建新的source元素
  const source = document.createElement('source');
  source.src = src;
  source.type = type || getAudioMimeType(src);
  
  // 清除现有的source
  audioElement.innerHTML = '';
  audioElement.appendChild(source);
  
  // 加载新音频
  audioElement.load();
};
