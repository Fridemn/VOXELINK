<template>
  <div class="card">
    <h2 class="text-xl font-semibold text-center text-gray-700 mb-4">语音交互</h2>
    <div class="btn-group">
      <button id="start-record-btn" class="primary" 
              @click="$emit('start-record')" 
              :disabled="startRecordBtnDisabled">
        开始实时对话
      </button>
      <button id="stop-record-btn" class="secondary" 
              @click="$emit('stop-record')" 
              :disabled="stopRecordBtnDisabled">
        停止对话
      </button>
    </div>
    <div class="status">{{ statusText }}</div>
    
    <div v-if="isVoiceChatting" class="voice-status mt-2">
      <div class="status-text text-center">正在聆听...</div>
      <div class="voice-indicator mx-auto mt-2" :class="{ active: isSpeaking }"></div>
    </div>
    
    <div v-if="progressWidth && progressWidth !== '0%'" class="recording-progress mt-3">
      <div class="bg-gray-200 rounded-full h-2.5 overflow-hidden">
        <div class="bg-blue-600 h-full" :style="{ width: progressWidth }"></div>
      </div>
      <div class="text-xs text-center mt-1 text-gray-600">{{ progressText }}</div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'VoiceInteraction',
  props: {
    startRecordBtnDisabled: {
      type: Boolean,
      default: false
    },
    stopRecordBtnDisabled: {
      type: Boolean,
      default: true
    },
    progressWidth: {
      type: String,
      default: '0%'
    },
    progressText: {
      type: String,
      default: '0%'
    },
    statusText: {
      type: String,
      default: '准备就绪'
    },
    isVoiceChatting: {
      type: Boolean,
      default: false
    },
    isSpeaking: {
      type: Boolean,
      default: false
    }
  },
  emits: ['start-record', 'stop-record']
};
</script>

<style scoped>
.voice-indicator {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background-color: #ccc;
}

.voice-indicator.active {
  background-color: #4CAF50;
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0% { transform: scale(1); }
  50% { transform: scale(1.2); }
  100% { transform: scale(1); }
}

.voice-status {
  padding: 8px;
  background-color: #f0f9ff;
  border-radius: 4px;
}
</style>
