<template>
  <!-- Live2D模型显示 -->
  <Live2dModel 
    :canvasSize="canvasSize"
    :speaking="isSpeaking"
    :audioUrl="currentAudioUrl"
    @speaking-change="updateSpeakingState"
    @play-audio="playAudio"
  />
  
  <!-- 设置面板 -->
  <Live2dSettings
    :modelList="modelList"
    :selectedModel="selectedModel"
    :isProcessing="isProcessing"
    :isPanelHidden="isSettingsPanelHidden"
    @panel-state-change="updatePanelState"
    @model-selection-change="updateModelSelection"
    @play-motion="playRandomMotion"
    @play-expression="playRandomExpression"
    @update-model="updateModel"
  />
  
  <!-- 加载和错误提示 -->
  <transition name="fade">
    <div v-if="loadingError" class="error-message">
      <h2>加载错误</h2>
      <p>{{ loadingError }}</p>
      <button class="primary-btn" @click="goHome">返回首页</button>
    </div>
  </transition>
  
  <transition name="fade">
    <div v-if="isLoading" class="loading-overlay">
      <div class="loader"></div>
      <p>加载中，请稍候...</p>
    </div>
  </transition>
</template>

<script>
import Live2dModelManager from './Live2dModel.js';
import Live2dModel from './Live2dModel.vue';
import Live2dSettings from './Live2dSettings.vue';

export default {
  name: 'Live2dEdgeTTS',
  components: {
    Live2dModel,
    Live2dSettings
  },
  props: {
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
      isSpeaking: false,
      currentAudioUrl: '',
      
      modelList: ['Hiyori', 'March 7th', 'MuraSame'],
      selectedModel: 'March 7th',
      live2dModel: null,
      modelLoaded: false,
      
      isProcessing: false,
      isLoading: true,
      loadingError: null,
      isSettingsPanelHidden: false,
      
      eyesFollow: true,
      
      motions: [],
      expressions: [],
      
      mouthOpenValue: 0,
      mouthUpdateInterval: null,
      audioContext: null,
      audioSource: null,
      audioAnalyser: null,
      frequencyData: null,
      
      mouthOpenParamName: null,
      usingBuiltInSpeech: false,

      canvasSize: {
        width: 600,
        height: 600
      },
      modelSize: {
        width: 300,
        height: 500
      },
      scaleFactor: 1.0,
      
      modelManager: null,
      currentPlayingAudioId: null,
    }
  },
  
  async mounted() {
    try {
      this.modelManager = new Live2dModelManager(this);
      
      this.loadSettingsPanelState();
      
      window.AudioContext = window.AudioContext || window.webkitAudioContext;
      
      window.addEventListener('ai-audio-play', this.handleGlobalAudioPlay);
      window.addEventListener('ai-audio-pause', this.handleGlobalAudioPause);
      window.addEventListener('ai-audio-ended', this.handleGlobalAudioEnded);
      
      this.isSpeaking = this.speaking;
      this.currentAudioUrl = this.audioUrl;
      
      await this.initializeApplication();
    } catch (error) {
      console.error('初始化失败:', error);
      this.loadingError = `初始化失败: ${error.message}`;
      this.isLoading = false;
    }
  },
  
  beforeUnmount() {
    window.removeEventListener('ai-audio-play', this.handleGlobalAudioPlay);
    window.removeEventListener('ai-audio-pause', this.handleGlobalAudioPause);
    window.removeEventListener('ai-audio-ended', this.handleGlobalAudioEnded);
  },
  
  watch: {
    speaking(newVal) {
      this.isSpeaking = newVal;
    },
    audioUrl(newUrl) {
      this.currentAudioUrl = newUrl;
    },
    eyesFollow(newValue) {
      this.setCookie('eyes', newValue.toString(), 30);
    },
    isSettingsPanelHidden(newVal) {
      localStorage.setItem('live2d_settings_hidden', newVal.toString());
    },
  },
  
  methods: {
    async initializeApplication() {
      try {
        this.loadModelConfig(); 
        this.loadSettingsFromCookies();
        this.setWhiteBackground();
        this.checkScriptsLoaded();
      } catch (error) {
        console.error('初始化应用时出错:', error);
        throw error;
      }
    },
    
    loadModelConfig() {
      try {
        const savedModel = localStorage.getItem('selectedModel');
        if (savedModel) {
          this.selectedModel = savedModel;
        }
        
        this.modelList = this.modelManager.getAvailableModels();
        
        const storedModelList = localStorage.getItem('modelList');
        if (storedModelList) {
          try {
            const savedList = JSON.parse(storedModelList);
            if (Array.isArray(savedList) && savedList.length > 0) {
              this.modelList = savedList;
            }
          } catch (e) {
            console.error('解析存储的模型列表失败:', e);
          }
        }
      } catch (error) {
        console.error('加载本地配置失败:', error);
        this.selectedModel = 'Hiyori';
      }
    },
    
    setWhiteBackground() {
      const canvas = document.getElementById("canvas");
      if (canvas) {
        canvas.style.backgroundColor = 'transparent';
        canvas.style.backgroundImage = 'none';
        canvas.style.border = 'none';
      }
    },
    
    checkScriptsLoaded() {
      try {
        if (window.PIXI && window.PIXI.live2d) {
          this.modelManager.initLive2D();
        } else {
          this.loadingError = '未能加载Live2D必要的库文件，请确保js文件夹中包含所有需要的脚本';
        }
      } catch (error) {
        console.error('检查脚本时发生错误:', error);
        this.loadingError = `检查脚本时发生错误: ${error.message}`;
      } finally {
        this.isLoading = false;
      }
    },
    
    playRandomMotion() {
      this.modelManager.playRandomMotion();
    },
    
    playRandomExpression() {
      this.modelManager.playRandomExpression();
    },
    
    updateModel(model) {
      if (this.isProcessing) return;
      this.isProcessing = true;
      
      try {
        const modelPath = `/src/assets/models/${model}/`;
        
        localStorage.setItem('selectedModel', model);
        
        location.reload();
      } catch (error) {
        console.error('更新模型失败:', error);
        alert('更新模型失败: ' + error.message);
      } finally {
        this.isProcessing = false;
      }
    },
    
    playAudio(url) {
      this.modelManager.playAudio(url);
    },
    
    updateSpeakingState(isSpeaking) {
      this.isSpeaking = isSpeaking;
      if (!isSpeaking) {
        this.modelManager.stopSpeaking();
      }
    },

    handleGlobalAudioPlay(event) {
      console.log('Live2dView: 收到全局音频播放事件', event.detail);
      
      const isNewSegment = event.detail.isNewSegment;
      const isSegmented = event.detail.isSegmented;
      
      // 如果是连续音频的一部分，使用特殊处理
      if (isNewSegment || isSegmented) {
        // 对于连续分段音频，我们保持当前状态
        if (this.isSpeaking) {
          console.log('继续使用当前口型状态进行播放');
          
          // 更新音频URL但保持说话状态
          if (event.detail && event.detail.audioUrl) {
            this.currentAudioUrl = event.detail.audioUrl;
          }
          return;
        }
      }
      
      // 常规处理
      if (this.currentPlayingAudioId === event.detail.sourceElementId) {
        console.log('忽略来自相同音频源的播放事件，避免重复播放');
        return;
      }
      
      this.currentPlayingAudioId = event.detail.sourceElementId || Date.now();
      this.isSpeaking = true;
      
      if (event.detail && event.detail.audioUrl) {
        this.currentAudioUrl = event.detail.audioUrl;
      }
    },
    
    handleGlobalAudioPause() {
      // 暂停时不做特殊处理，因为可能是临时暂停
    },
    
    handleGlobalAudioEnded(event) {
      console.log('Live2dView: 收到全局音频结束事件', event.detail);
      
      // 判断是否是最后一段音频
      const isFinalSegment = event.detail && event.detail.finalSegment;
      
      // 如果是分段音频但不是最后一段，保持说话状态
      if (!isFinalSegment && event.detail && (event.detail.isSegmented || event.detail.hasNextSegment)) {
        console.log('有下一段音频，保持说话状态');
        return;
      }
      
      // 所有音频段播放结束，停止说话
      this.currentPlayingAudioId = null;
      this.isSpeaking = false;
      this.currentAudioUrl = '';
      this.modelManager.stopSpeaking();
    },

    getCookie(name) {
      const value = `; ${document.cookie}`;
      const parts = value.split(`; ${name}=`);
      if (parts.length === 2) return parts.pop().split(';').shift();
    },
    
    setCookie(name, value, days) {
      const date = new Date();
      date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
      const expires = `expires=${date.toUTCString()}`;
      document.cookie = `${name}=${value}; ${expires}; path=/`;
    },
    
    loadSettingsFromCookies() {
      const eyesValue = this.getCookie("eyes");
      if (eyesValue === "false") this.eyesFollow = false;
    },
    
    goHome() {
      this.$router.push('/');
    },
    
    updatePanelState(isPanelHidden) {
      this.isSettingsPanelHidden = isPanelHidden;
    },
    
    updateModelSelection(model) {
      this.selectedModel = model;
    },
    
    loadSettingsPanelState() {
      const panelHidden = localStorage.getItem('live2d_settings_hidden');
      if (panelHidden === 'true') {
        this.isSettingsPanelHidden = true;
      }
    },
    
    setMouthOpenValue(value) {
      if (this.modelManager && typeof this.modelManager.setMouthOpen === 'function') {
        this.modelManager.setMouthOpen(value);
      }
    },
  }
}
</script>

<style scoped>
.loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(255, 255, 255, 0.8);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  z-index: 1100;
}

.loader {
  border: 5px solid #f3f3f3;
  border-top: 5px solid #42b983;
  border-radius: 50%;
  width: 50px;
  height: 50px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.error-message {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background-color: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 0 20px rgba(0, 0, 0, 0.2);
  z-index: 1100;
  max-width: 80%;
  text-align: center;
}

.primary-btn {
  background-color: #42b983;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 6px 12px;
  cursor: pointer;
  font-size: 14px;
}

.fade-enter-active, .fade-leave-active {
  transition: opacity 0.5s;
}

.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
</style>
