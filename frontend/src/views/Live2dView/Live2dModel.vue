<template>
  <!-- 动态大小的模型容器 -->
  <div class="model-container" ref="containerRef">
    <!-- canvas元素 -->
    <canvas id="canvas" class="live2d-canvas"></canvas>
  </div>
</template>

<script>
export default {
  name: 'Live2dModel',
  props: {
    canvasSize: {
      type: Object,
      required: true
    },
    speaking: {
      type: Boolean,
      default: false
    },
    audioUrl: {
      type: String,
      default: ''
    }
  },
  
  data() {
    return {
      // 语音相关
      isSpeaking: false,
      
      // 音频监听相关
      audioElements: [],
      currentAudioSourceId: null,
      processedAudioIds: new Set(),
      
      // 添加分段音频追踪
      segmentedAudioInfo: {
        isSegmented: false,
        currentSegment: 0,
        lastSegmentTime: 0
      }
    }
  },
  
  mounted() {
    // 监听全局音频播放事件
    window.addEventListener('ai-audio-play', this.handleGlobalAudioPlay);
    window.addEventListener('ai-audio-pause', this.handleGlobalAudioPause);
    window.addEventListener('ai-audio-ended', this.handleGlobalAudioEnd);
    
    // 为页面上已有的音频元素添加监听
    this.attachAudioListenersToExistingElements();
    
    // 监听DOM变化，为新增的音频元素添加监听
    this.setupMutationObserver();
    console.log('Live2dModel组件已挂载，开始监听音频事件');
  },
  
  beforeUnmount() {
    // 移除事件监听
    window.removeEventListener('ai-audio-play', this.handleGlobalAudioPlay);
    window.removeEventListener('ai-audio-pause', this.handleGlobalAudioPause);
    window.removeEventListener('ai-audio-ended', this.handleGlobalAudioEnd);
    
    this.detachAllAudioListeners();
    
    if (this.observer) {
      this.observer.disconnect();
    }
  },
  
  watch: {
    speaking(newVal) {
      console.log('Live2dModel: speaking prop变化:', newVal);
      if (newVal !== this.isSpeaking) {
        this.isSpeaking = newVal;
        this.$emit('speaking-change', newVal);
      }
    },
    
    audioUrl(newUrl) {
      console.log('Live2dModel: audioUrl prop变化:', newUrl);
      if (newUrl && this.speaking) {
        this.$emit('play-audio', newUrl);
      }
    },
  },
  
  methods: {
    setupMutationObserver() {
      this.observer = new MutationObserver(mutations => {
        mutations.forEach(mutation => {
          if (mutation.type === 'childList') {
            mutation.addedNodes.forEach(node => {
              if (node.nodeType === Node.ELEMENT_NODE) {
                if (node.nodeName.toLowerCase() === 'audio') {
                  this.attachAudioListeners(node);
                } else {
                  const audioElements = node.querySelectorAll('audio');
                  audioElements.forEach(audio => {
                    this.attachAudioListeners(audio);
                  });
                }
              }
            });
          }
        });
      });
      
      this.observer.observe(document.body, {
        childList: true,
        subtree: true
      });
    },
    
    attachAudioListenersToExistingElements() {
      const audioElements = document.querySelectorAll('audio');
      console.log(`找到${audioElements.length}个已存在的音频元素`);
      audioElements.forEach(audio => {
        this.attachAudioListeners(audio);
      });
    },
    
    attachAudioListeners(audio) {
      if (this.audioElements.includes(audio)) return;
      
      audio.addEventListener('play', this.handleAudioPlay);
      audio.addEventListener('pause', this.handleAudioPause);
      audio.addEventListener('ended', this.handleAudioEnd);
      
      this.audioElements.push(audio);
    },
    
    detachAllAudioListeners() {
      this.audioElements.forEach(audio => {
        audio.removeEventListener('play', this.handleAudioPlay);
        audio.removeEventListener('pause', this.handleAudioPause);
        audio.removeEventListener('ended', this.handleAudioEnd);
      });
      this.audioElements = [];
    },
    
    handleGlobalAudioPlay(event) {
      console.log('收到全局音频播放事件', event.detail);
      const sourceId = event.detail.sourceElementId;
      const isSegmented = event.detail.isSegmented || event.detail.isNewSegment || false;
      
      // 已处理过的音频ID或已经在说话且是分段音频，跳过重复处理
      if (this.processedAudioIds.has(sourceId) || 
          (this.isSpeaking && isSegmented)) {
        return;
      }
      
      // 记录当前音频ID并更新状态
      this.processedAudioIds.add(sourceId);
      this.currentAudioSourceId = sourceId;
      
      // 处理分段音频逻辑
      if (isSegmented) {
        this.segmentedAudioInfo = {
          isSegmented: true,
          currentSegment: event.detail.segmentIndex || 0,
          lastSegmentTime: Date.now()
        };
      }
      
      // 更新说话状态
      if (!this.isSpeaking) {
        this.isSpeaking = true;
        this.$emit('speaking-change', true);
      }
    },
    
    handleGlobalAudioPause(event) {
      console.log('收到全局音频暂停事件');
    },
    
    handleGlobalAudioEnd(event) {
      // 只有在收到最终段落结束事件时才停止说话
      const isFinalSegment = event.detail && event.detail.finalSegment;
      
      if (!isFinalSegment && this.segmentedAudioInfo.isSegmented) {
        // 清理当前音频ID但保持说话状态
        if (this.currentAudioSourceId) {
          this.processedAudioIds.delete(this.currentAudioSourceId);
          this.currentAudioSourceId = null;
        }
        return;
      }
      
      // 所有音频播放结束，重置状态
      this.processedAudioIds.clear();
      this.currentAudioSourceId = null;
      this.segmentedAudioInfo = {
        isSegmented: false,
        currentSegment: 0,
        lastSegmentTime: 0
      };
      
      this.isSpeaking = false;
      this.$emit('speaking-change', false);
    },
    
    handleAudioPlay(event) {
      if (this.processedAudioIds.has(event.target.id)) {
        console.log('已通过全局事件处理过此音频，忽略直接事件');
        return;
      }
      
      const isAIAudio = !event.target.classList.contains('user-audio');
      
      if (isAIAudio) {
        if (!event.target.id) {
          event.target.id = 'audio-' + Date.now();
        }
        
        const detail = { sourceElementId: event.target.id };
        window.dispatchEvent(new CustomEvent('ai-audio-play', { detail }));
      }
    },
    
    handleAudioPause(event) {
      const isAIAudio = !event.target.classList.contains('user-audio');
      if (isAIAudio) {
        const detail = { sourceElementId: event.target.id };
        window.dispatchEvent(new CustomEvent('ai-audio-pause', { detail }));
      }
    },
    
    handleAudioEnd(event) {
      const isAIAudio = !event.target.classList.contains('user-audio');
      if (isAIAudio) {
        const detail = { sourceElementId: event.target.id, finalSegment: true };
        window.dispatchEvent(new CustomEvent('ai-audio-ended', { detail }));
      }
    }
  }
}
</script>

<style scoped>
.model-container {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 1000;
  pointer-events: none; /* 禁止鼠标事件 */
}

.live2d-canvas {
  background-color: transparent;
  border: none;
}
</style>
