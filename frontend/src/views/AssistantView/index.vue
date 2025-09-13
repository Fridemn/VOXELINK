<template>
  <div class="max-w-4xl mx-auto px-4 py-8">
    <h1 class="text-3xl font-bold text-center text-gray-800 mb-8">语音助手演示</h1>
    
    <div class="card">
      <h2 class="text-xl font-semibold text-gray-700 mb-4">连接设置</h2>
      <div class="config-panel">
        <div class="config-row">
          <label for="stt-url">STT WebSocket:</label>
          <input id="stt-url" type="text" v-model="sttApiUrl" :disabled="isConnected" class="font-mono">
        </div>
        <div class="config-row">
          <label for="tts-url">TTS WebSocket:</label>
          <input id="tts-url" type="text" v-model="ttsApiUrl" :disabled="isConnected" class="font-mono">
        </div>
        <div class="config-row">
          <label for="user-token">用户令牌:</label>
          <input id="user-token" type="text" v-model="userToken" :disabled="isConnected" class="font-mono">
        </div>
      </div>
    </div>

    <ConnectionSettings 
      :api-url="''"
      :is-connected="isConnected"
      :connection-status-text="connectionStatusText"
      :connection-status-class="connectionStatusClass"
      :connect-btn-disabled="connectBtnDisabled"
      :disconnect-btn-disabled="disconnectBtnDisabled"
      @connect="connectWebSocket"
      @disconnect="disconnectWebSocket"
    />
    
    <VoiceInteraction
      :start-record-btn-disabled="startRecordBtnDisabled"
      :stop-record-btn-disabled="stopRecordBtnDisabled"
      :progress-width="progressWidth"
      :progress-text="progressText"
      :status-text="statusText"
      :is-voice-chatting="isRecording"
      :is-speaking="isSpeaking"
      @start-record="startVoiceChat"
      @stop-record="stopVoiceChat"
    />
    
    <ConversationHistory :conversation-history="conversationHistory" />
    
    <AudioOutput 
      ref="audioPlayerComponent"
      :current-audio="currentAudio"
      :audio-queue="audioQueue"
      :muted="shouldMuteLocalAudio"
      @audio-ended="onAudioEnded"
      @audio-error="onAudioError"
      @audio-load-start="onAudioLoadStart"
      @audio-can-play="onAudioCanPlay"
    />
    
    <LogPanel :logs="logs" />
    
    <!-- 添加纯白区域，高度为90vh -->
    <div class="white-space bg-white h-[90vh] w-full mt-8"></div>
  </div>
</template>

<script>
import { ref, onMounted, computed, inject, onUnmounted } from 'vue'; // 添加onUnmounted引入
import ConnectionSettings from './components/ConnectionSettings.vue';
import VoiceInteraction from './components/VoiceInteraction.vue';
import ConversationHistory from './components/ConversationHistory.vue';
import AudioOutput from './components/AudioOutput.vue';
import LogPanel from './components/LogPanel.vue';

export default {
  name: 'HomeView',
  components: {
    ConnectionSettings,
    VoiceInteraction,
    ConversationHistory,
    AudioOutput,
    LogPanel
  },
  setup() {
    // 获取Live2D控制接口
    const live2dControls = inject('live2dControls');

    // --- 音频处理配置 ---
    const AUDIO_CONFIG = {
      SAMPLE_RATE: 16000,
      CHANNELS: 1,
      CHUNK_SIZE: 2048,
      AUDIO_RMS_THRESHOLD: 0.05, // VAD RMS 阈值
      SPEECH_PADDING_FRAMES: 2,  // 语音结束后保留的音频帧数
      MAX_SILENCE_FRAMES: 8,     // 判定为一句话结束的最大静音帧数
    };

    // --- WebSocket and Connection State ---
    const sttSocket = ref(null);
    const ttsSocket = ref(null);
    const isSttConnected = ref(false);
    const isTtsConnected = ref(false);

    // --- Audio Recording State ---
    const audioContext = ref(null);
    const mediaStream = ref(null);
    const audioProcessor = ref(null);
    const speechFrames = ref([]);
    const silenceFrames = ref(0);
    const isClientSpeaking = ref(false);

    // Reactive data
    const isRecording = ref(false);
    const lastServerActivity = ref(Date.now());
    const isSpeaking = ref(false); // 来自服务端的语音活动状态

    const sttApiUrl = ref('ws://115.25.46.11:8765/ws');
    const ttsApiUrl = ref('ws://115.25.46.11:9880');
    const userToken = ref('eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiMzFmM2U1NjYtYzg1YS00NjY5LWEyMWEtNTViZGIwZDgyZTZlIn0.rxFWlGL6jeF1zc9wlSs0qErd33yYCDO_7D6thaEtivE');

    const statusText = ref('等待连接...');
    const connectionStatusText = ref('未连接');
    const conversationHistory = ref([{ sender: 'assistant', text: '您好，我是语音助手，请点击"连接服务器"开始对话。' }]);
    const logs = ref([]);
    const audioQueue = ref([]);
    const isPlaying = ref(false);
    const connectionStatusClass = ref('disconnected');
    const progressWidth = ref('0%');
    const progressText = ref('0%');
    const currentAudio = ref(null);
    
    // Computed properties
    const isConnected = computed(() => isSttConnected.value && isTtsConnected.value);
    const connectBtnDisabled = computed(() => isSttConnected.value || isTtsConnected.value);
    const disconnectBtnDisabled = computed(() => !isSttConnected.value && !isTtsConnected.value);
    const startRecordBtnDisabled = computed(() => {
      return !isConnected.value || isRecording.value;
    });
    const stopRecordBtnDisabled = computed(() => !isRecording.value);

    // 计算属性：当Live2D可见时，本地音频应该静音
    const shouldMuteLocalAudio = computed(() => {
      return !!(live2dControls && live2dControls.isVisible.value);
    });

    const connectWebSocket = () => {
      updateStatus('正在连接...');
      updateConnectionStatus('正在连接...', 'processing');
      connectSttSocket();
      connectTtsSocket();
    };

    const connectSttSocket = () => {
      if (sttSocket.value) sttSocket.value.close();
      addToLog(`STT: 尝试连接到 ${sttApiUrl.value}`);
      sttSocket.value = new WebSocket(sttApiUrl.value);
      sttSocket.value.onopen = () => {
        isSttConnected.value = true;
        addToLog('STT: WebSocket连接成功');
        updateCombinedConnectionStatus();
        updateSttServerConfig();
      };
      sttSocket.value.onmessage = handleSttMessage;
      sttSocket.value.onclose = () => {
        isSttConnected.value = false;
        addToLog('STT: WebSocket连接已关闭');
        if (isRecording.value) stopVoiceChat();
        updateCombinedConnectionStatus();
      };
      sttSocket.value.onerror = (err) => {
        isSttConnected.value = false;
        addToLog(`STT: WebSocket错误: ${err}`, 'error');
        updateCombinedConnectionStatus();
      };
    };

    const connectTtsSocket = () => {
      if (ttsSocket.value) ttsSocket.value.close();
      const ttsWsUrl = `${ttsApiUrl.value}/ws/${encodeURIComponent(userToken.value)}`;
      addToLog(`TTS: 尝试连接到 ${ttsWsUrl}`);
      ttsSocket.value = new WebSocket(ttsWsUrl);
      ttsSocket.value.onopen = () => {
        isTtsConnected.value = true;
        addToLog('TTS: WebSocket连接成功');
        updateCombinedConnectionStatus();
      };
      ttsSocket.value.onmessage = handleTtsMessage;
      ttsSocket.value.onclose = () => {
        isTtsConnected.value = false;
        addToLog('TTS: WebSocket连接已关闭');
        updateCombinedConnectionStatus();
      };
      ttsSocket.value.onerror = (err) => {
        isTtsConnected.value = false;
        addToLog(`TTS: WebSocket错误: ${err}`, 'error');
        updateCombinedConnectionStatus();
      };
    };

    const updateCombinedConnectionStatus = () => {
      if (isSttConnected.value && isTtsConnected.value) {
        updateConnectionStatus('已连接', 'connected');
        updateStatus('已连接，请开始对话');
      } else if (!isSttConnected.value && !isTtsConnected.value) {
        updateConnectionStatus('未连接', 'disconnected');
        updateStatus('连接已断开');
      } else {
        let status = [];
        if (isSttConnected.value) status.push('STT已连接');
        else status.push('STT未连接');
        if (isTtsConnected.value) status.push('TTS已连接');
        else status.push('TTS未连接');
        updateConnectionStatus(status.join(', '), 'processing');
        updateStatus('部分服务连接中...');
      }
    };
    
    const disconnectWebSocket = () => {
      if (sttSocket.value) sttSocket.value.close(1000, '用户主动断开');
      if (ttsSocket.value) ttsSocket.value.close(1000, '用户主动断开');
      stopVoiceChat();
      resetConnectionState();
      addToLog('已断开所有连接');
    };

    // Update connection status
    const updateConnectionStatus = (message, status) => {
      connectionStatusText.value = message;
      connectionStatusClass.value = status;
    };

    // Reset connection state
    const resetConnectionState = () => {
      isSttConnected.value = false;
      isTtsConnected.value = false;
      updateCombinedConnectionStatus();
      if (isRecording.value) stopVoiceChat();
      progressWidth.value = '0%';
      progressText.value = '0%';
    };

    const updateSttServerConfig = () => {
      if (!sttSocket.value || sttSocket.value.readyState !== WebSocket.OPEN) {
        addToLog('STT WebSocket未连接，无法更新配置');
        return;
      }
      const params = {
        action: 'config',
        data: {
          user_token: userToken.value,
        }
      };
      sttSocket.value.send(JSON.stringify(params));
      addToLog('已更新STT会话参数 (用户令牌)');
    };

    const startVoiceChat = async () => {
      if (!isConnected.value) {
        addToLog('服务未完全连接', 'error');
        return;
      }
      if (isRecording.value) return;

      updateSttServerConfig();

      try {
        mediaStream.value = await navigator.mediaDevices.getUserMedia({
          audio: {
            sampleRate: AUDIO_CONFIG.SAMPLE_RATE,
            channelCount: AUDIO_CONFIG.CHANNELS,
            echoCancellation: true,
            noiseSuppression: true
          }
        });

        audioContext.value = new (window.AudioContext || window.webkitAudioContext)({
          sampleRate: AUDIO_CONFIG.SAMPLE_RATE
        });
        
        const source = audioContext.value.createMediaStreamSource(mediaStream.value);
        audioProcessor.value = audioContext.value.createScriptProcessor(
          AUDIO_CONFIG.CHUNK_SIZE, 1, 1
        );
        
        source.connect(audioProcessor.value);
        audioProcessor.value.connect(audioContext.value.destination);

        audioProcessor.value.onaudioprocess = (e) => processAudio(e);

        isRecording.value = true;
        updateStatus('正在聆听...');
        addToLog('录音已开始');

      } catch (error) {
        addToLog(`录音失败: ${error.message}`, 'error');
        console.error('Error starting recording:', error);
      }
    };
    
    const processAudio = (e) => {
      if (!isRecording.value) return;

      const inputData = e.inputBuffer.getChannelData(0);
      const rms = Math.sqrt(inputData.reduce((sum, val) => sum + val * val, 0) / inputData.length);
      const isSpeech = rms > AUDIO_CONFIG.AUDIO_RMS_THRESHOLD;
      isSpeaking.value = isSpeech; // Update client-side speaking status for UI

      const audioData = new Int16Array(inputData.map(n => Math.max(-32768, Math.min(32767, n * 32768))));

      if (isSpeech) {
        if (!isClientSpeaking.value) {
          isClientSpeaking.value = true;
          updateStatus('检测到语音...');
        }
        speechFrames.value.push(audioData);
        silenceFrames.value = 0;
      } else if (isClientSpeaking.value) {
        silenceFrames.value++;
        if (silenceFrames.value <= AUDIO_CONFIG.SPEECH_PADDING_FRAMES) {
          speechFrames.value.push(audioData);
        }
        if (silenceFrames.value >= AUDIO_CONFIG.MAX_SILENCE_FRAMES) {
          if (speechFrames.value.length > 0) {
            const audioBuffer = concatenateAudioChunks(speechFrames.value);
            sendAudioToServer(audioBuffer);
          }
          isClientSpeaking.value = false;
          speechFrames.value = [];
          updateStatus('正在聆听...');
        }
      }
    };
    
    const concatenateAudioChunks = (chunks) => {
      const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
      const result = new Int16Array(totalLength);
      let offset = 0;
      for (const chunk of chunks) {
        result.set(chunk, offset);
        offset += chunk.length;
      }
      return result;
    };

    const sendAudioToServer = (audioBuffer) => {
      if (!sttSocket.value || sttSocket.value.readyState !== WebSocket.OPEN) return;
      const base64Audio = btoa(String.fromCharCode.apply(null, new Uint8Array(audioBuffer.buffer)));
      const message = {
        action: "audio",
        data: { audio_data: base64Audio, format: "pcm" }
      };
      sttSocket.value.send(JSON.stringify(message));
    };

    const stopVoiceChat = () => {
      if (!isRecording.value) return;

      isRecording.value = false;
      isClientSpeaking.value = false;
      isSpeaking.value = false;
      
      if (audioProcessor.value) audioProcessor.value.disconnect();
      if (audioContext.value) audioContext.value.close();
      if (mediaStream.value) mediaStream.value.getTracks().forEach(track => track.stop());

      audioProcessor.value = null;
      audioContext.value = null;
      mediaStream.value = null;
      speechFrames.value = [];

      addToLog('录音已停止');
      updateStatus('已停止');
    };

    const handleSttMessage = (event) => {
      lastServerActivity.value = Date.now();
      const message = JSON.parse(event.data);

      const logContent = JSON.stringify(message).substring(0, 150);
      addToLog(`STT: ${logContent}`);

      switch (message.type) {
        case 'recognition_result':
          handleRecognitionResult(message);
          break;
        case 'llm_response':
          handleLLMResponse(message.data);
          break;
        case 'error':
          updateStatus(`错误: ${message.error}`);
          addToLog(`STT 错误: ${message.error}`, 'error');
          break;
        default:
          if (message.message) {
             addToLog(`STT 信息: ${message.message}`);
          }
      }
    };

    const handleTtsMessage = (event) => {
      if (event.data === 'pong') {
        console.log('TTS pong received');
        return;
      }
      try {
        const message = JSON.parse(event.data);
        if (message.type !== 'audio') return;

        addToLog(`TTS: 收到音频 "${message.text.substring(0, 20)}..."`, 'success');
        
        const audioBlob = base64ToBlob(message.audio_base64, 'audio/wav');
        const audioUrl = URL.createObjectURL(audioBlob);

        audioQueue.value.push({
          url: audioUrl,
          text: message.text,
          isBlob: true, // 标记为blob以便后续清理
        });
        
        if (!isPlaying.value) {
          playNextAudio();
        }
      } catch (e) {
        addToLog(`TTS: 消息解析失败: ${e.message}`, 'error');
      }
    };

    const base64ToBlob = (base64, mimeType) => {
      const byteChars = atob(base64);
      const byteNumbers = new Array(byteChars.length);
      for (let i = 0; i < byteChars.length; i++) {
        byteNumbers[i] = byteChars.charCodeAt(i);
      }
      return new Blob([new Uint8Array(byteNumbers)], { type: mimeType });
    };

    // 新增：处理语音识别结果
    const handleRecognitionResult = (message) => {
      const text = message.text || '';
      updateStatus(`已识别: ${text.substring(0, 30)}${text.length > 30 ? '...' : ''}`);
      addMessageToConversation(text, 'user');
      isSpeaking.value = false; // from server
    };
    
    const handleLLMResponse = (data) => {
        updateStatus('LLM处理完成，等待语音...');
        addMessageToConversation(data.text, 'assistant');
    };

    // Update status
    const updateStatus = (message) => {
      statusText.value = message;
      console.log('Status:', message);
    };

    // Add message to conversation
    const addMessageToConversation = (text, sender, className = '') => {
      conversationHistory.value.push({ sender: sender, text: text, className: className });
    };

    // Add log
    const addToLog = (message) => {
      const now = new Date();
      const timeStr = now.toLocaleTimeString();
      logs.value.push(`[${timeStr}] ${message}`);
    };

    // Handle audio events - 修改为支持连续音频的口型同步
    const onAudioEnded = () => {
      addToLog('音频播放完成');
      
      const finishedAudio = audioQueue.value[0];
      if (finishedAudio && finishedAudio.isBlob) {
        URL.revokeObjectURL(finishedAudio.url); // 释放Blob URL
        addToLog(`释放Blob URL: ${finishedAudio.url}`);
      }
      
      // 检查是否有下一段音频
      const hasNextAudio = audioQueue.value.length > 1;
      
      // 移除已播放的音频
      audioQueue.value.shift();
      isPlaying.value = false;
      currentAudio.value = null;
      
      // 如果没有下一段音频，才停止Live2D说话
      if (!hasNextAudio && live2dControls) {
        console.log('AssistantView: 通知Live2D停止说话 (所有音频播放完毕)');
        live2dControls.stopSpeaking();
        
        // 派发全局音频结束事件
        dispatchAudioEvent('ai-audio-ended', {
          finalSegment: true
        });
      }
      
      // 继续播放队列中的下一个
      if (audioQueue.value.length > 0) {
        setTimeout(() => playNextAudio(), 50); // 短暂延迟确保事件处理完成
      }
    };
    
    // 自定义音频事件派发
    const dispatchAudioEvent = (eventName, detail = {}) => {
      try {
        const event = new CustomEvent(eventName, {
          bubbles: true,
          detail: detail
        });
        window.dispatchEvent(event);
        console.log(`AssistantView: 派发${eventName}事件:`, detail);
      } catch (error) {
        console.error(`AssistantView: 派发${eventName}事件失败:`, error);
      }
    };

    const onAudioError = (error) => {
      console.error('音频播放错误:', error);
      addToLog(`音频播放错误: ${error.message || '未知错误'}`);
      
      // 跳过错误的音频
      isPlaying.value = false;
      audioQueue.value.shift();
      currentAudio.value = null;
      
      // 尝试播放下一个
      playNextAudio();
    };

    const onAudioLoadStart = () => {
      // Placeholder for any actions on load start
    };

    const onAudioCanPlay = () => {
      // Placeholder for any actions when audio is ready to play
    };

    // Play next audio in queue - 修改为支持连续口型同步
    const playNextAudio = () => {
      if (audioQueue.value.length === 0 || isPlaying.value) return;
      
      currentAudio.value = audioQueue.value[0];
      isPlaying.value = true;
      
      // 生成唯一ID
      const audioId = 'assistant-audio-' + Date.now();
      currentAudio.value.id = audioId;
      
      // 通知Live2D和发送全局事件
      if (live2dControls && live2dControls.isVisible.value) {
        live2dControls.speak(currentAudio.value.url);
        dispatchAudioEvent('ai-audio-play', {
          audioUrl: currentAudio.value.url,
          sourceElementId: audioId,
          isNewSegment: true,
          text: currentAudio.value.text
        });
      }
    };

    // Lifecycle hook
    onMounted(() => {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        updateStatus('您的浏览器不支持录音功能');
        addToLog('错误: 浏览器不支持录音功能');
        return;
      }

      addToLog('页面已加载，请点击"连接"按钮连接到WebSocket服务器');
    });
    
    // 在组件卸载时清理资源
    onUnmounted(() => {
      disconnectWebSocket();
      if (audioContext.value && audioContext.value.state !== 'closed') {
        audioContext.value.close();
      }
    });

    return {
      isRecording,
      isConnected,
      sttApiUrl,
      ttsApiUrl,
      userToken,
      statusText,
      connectionStatusText,
      conversationHistory,
      logs,
      audioQueue,
      isPlaying,
      connectionStatusClass,
      progressWidth,
      progressText,
      connectBtnDisabled,
      disconnectBtnDisabled,
      startRecordBtnDisabled,
      stopRecordBtnDisabled,
      connectWebSocket,
      disconnectWebSocket,
      startVoiceChat,
      stopVoiceChat,
      updateStatus,
      addMessageToConversation,
      addToLog,
      onAudioEnded,
      onAudioError,
      onAudioLoadStart,
      onAudioCanPlay,
      playNextAudio,
      currentAudio,
      dispatchAudioEvent,
      shouldMuteLocalAudio,
      isSpeaking
    };
  }
};
</script>

<style>
/* 全局共享样式可以放在这里 */
.card {
  @apply bg-white rounded-lg shadow-md p-6 mb-6 border border-gray-200;
}

.btn-group {
  @apply flex flex-wrap justify-center gap-3 my-4;
}

.config-row {
  @apply flex flex-wrap items-center mb-4;
}

.config-panel {
  @apply mt-4;
}

.status {
  @apply text-center font-medium my-3;
}

.connected {
  @apply text-green-600;
}

.disconnected {
  @apply text-red-600;
}

.processing {
  @apply text-yellow-600;
}

label {
  @apply mr-2 w-32 text-gray-700;
}

input, select {
  @apply px-3 py-2 border border-gray-300 rounded-md flex-1 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent;
}

button {
  @apply px-4 py-2 rounded-md font-medium transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-opacity-50;
}

button.primary {
  @apply bg-green-600 text-white hover:bg-green-700 focus:ring-green-500;
}

button.secondary {
  @apply bg-red-600 text-white hover:bg-red-700 focus:ring-red-500;
}

button.neutral {
  @apply bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500;
}

button:disabled {
  @apply bg-gray-400 cursor-not-allowed hover:bg-gray-400;
}

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

/* 添加纯白区域的样式 */
.white-space {
  border-top: 1px solid #eaeaea;
}
</style>
