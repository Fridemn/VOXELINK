<template>
  <div class="live2d-container">
    <Live2dModel 
      :canvas-size="canvasSize" 
      :speaking="isSpeaking" 
      :audio-url="currentAudioUrl"
      :draggable="false"
    />
    <div class="controls">
      <button @click="toggleConnection" :disabled="isConnecting" class="connect-btn">
        {{ connectionButtonText }}
      </button>
    </div>
    <AudioOutput 
      ref="audioPlayerComponent"
      :current-audio="currentAudio"
      :audio-queue="audioQueue"
      :muted="false"
      @audio-ended="onAudioEnded"
      @audio-error="onAudioError"
      @audio-load-start="onAudioLoadStart"
      @audio-can-play="onAudioCanPlay"
      style="display: none;"
    />
  </div>
</template>

<script>
import { ref, onMounted, computed, onUnmounted } from 'vue';
import Live2dModel from '../Live2dView/Live2dModel.vue';
import AudioOutput from '../AssistantView/components/AudioOutput.vue';

export default {
  name: 'VoiceAssistantLive2d',
  components: {
    Live2dModel,
    AudioOutput,
  },
  setup() {
    const canvasSize = ref({ width: 0, height: 0 });

    const updateCanvasSize = () => {
      const screenHeight = window.innerHeight;
      // Assuming a model aspect ratio of 3:5 (width:height) based on other files
      const aspectRatio = 3 / 5; 
      const newWidth = screenHeight * aspectRatio;
      
      canvasSize.value = {
        width: newWidth,
        height: screenHeight
      };
    };

    // --- State from AssistantView ---
    const AUDIO_CONFIG = {
      SAMPLE_RATE: 16000,
      CHANNELS: 1,
      CHUNK_SIZE: 2048,
      AUDIO_RMS_THRESHOLD: 0.05,
      SPEECH_PADDING_FRAMES: 2,
      MAX_SILENCE_FRAMES: 8,
    };

    const sttSocket = ref(null);
    const ttsSocket = ref(null);
    const isSttConnected = ref(false);
    const isTtsConnected = ref(false);
    const audioContext = ref(null);
    const mediaStream = ref(null);
    const audioProcessor = ref(null);
    const speechFrames = ref([]);
    const silenceFrames = ref(0);
    const isClientSpeaking = ref(false);
    const isRecording = ref(false);
    const lastServerActivity = ref(Date.now());
    const sttApiUrl = ref('ws://115.25.46.11:8765/ws');
    const ttsApiUrl = ref('ws://115.25.46.11:9880');
    const userToken = ref('eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiMzFmM2U1NjYtYzg1YS00NjY5LWEyMWEtNTViZGIwZDgyZTZlIn0.rxFWlGL6jeF1zc9wlSs0qErd33yYCDO_7D6thaEtivE');
    const conversationHistory = ref([]);
    const logs = ref([]);
    const audioQueue = ref([]);
    const isPlaying = ref(false);
    const currentAudio = ref(null);
    const isConnected = computed(() => isSttConnected.value && isTtsConnected.value);
    const isConnecting = ref(false);

    const connectionButtonText = computed(() => {
      if (isConnecting.value) return '连接中...';
      return isConnected.value ? '断开连接' : '点击连接';
    });
    
    // --- State from Live2dView ---
    const isSpeaking = ref(false); // Used by Live2dModel
    const currentAudioUrl = ref(''); // Used by Live2dModel

    // --- Methods from AssistantView ---
    const addToLog = (message, type = 'info') => {
      const now = new Date();
      const timeStr = now.toLocaleTimeString();
      const logMessage = `[${timeStr}] ${message}`;
      logs.value.push(logMessage);
      console.log(`[${type.toUpperCase()}] ${logMessage}`);
    };
    
    const toggleConnection = () => {
      if (isConnected.value) {
        disconnectWebSocket();
      } else {
        connectWebSocket();
      }
    };
    
    const connectWebSocket = () => {
      isConnecting.value = true;
      addToLog('Attempting to connect...');
      connectSttSocket();
      connectTtsSocket();
    };

    const connectSttSocket = () => {
      if (sttSocket.value) sttSocket.value.close();
      addToLog(`STT: Connecting to ${sttApiUrl.value}`);
      sttSocket.value = new WebSocket(sttApiUrl.value);
      sttSocket.value.onopen = () => {
        isSttConnected.value = true;
        addToLog('STT: WebSocket connection successful');
        updateCombinedConnectionStatus();
        updateSttServerConfig();
      };
      sttSocket.value.onmessage = handleSttMessage;
      sttSocket.value.onclose = () => {
        isSttConnected.value = false;
        isConnecting.value = false;
        addToLog('STT: WebSocket connection closed');
        if (isRecording.value) stopVoiceChat();
        updateCombinedConnectionStatus();
      };
      sttSocket.value.onerror = (err) => {
        isSttConnected.value = false;
        isConnecting.value = false;
        addToLog(`STT: WebSocket error: ${err}`, 'error');
        updateCombinedConnectionStatus();
      };
    };

    const connectTtsSocket = () => {
      if (ttsSocket.value) ttsSocket.value.close();
      const ttsWsUrl = `${ttsApiUrl.value}/ws/${encodeURIComponent(userToken.value)}`;
      addToLog(`TTS: Connecting to ${ttsWsUrl}`);
      ttsSocket.value = new WebSocket(ttsWsUrl);
      ttsSocket.value.onopen = () => {
        isTtsConnected.value = true;
        addToLog('TTS: WebSocket connection successful');
        updateCombinedConnectionStatus();
      };
      ttsSocket.value.onmessage = handleTtsMessage;
      ttsSocket.value.onclose = () => {
        isTtsConnected.value = false;
        isConnecting.value = false;
        addToLog('TTS: WebSocket connection closed');
        updateCombinedConnectionStatus();
      };
      ttsSocket.value.onerror = (err) => {
        isTtsConnected.value = false;
        isConnecting.value = false;
        addToLog(`TTS: WebSocket error: ${err}`, 'error');
        updateCombinedConnectionStatus();
      };
    };
    
    const updateCombinedConnectionStatus = () => {
      if (isConnected.value) {
        isConnecting.value = false;
        addToLog('All services connected.');
        startVoiceChat(); // Automatically start listening
      } else {
        addToLog('Some services are not connected.');
      }
    };
    
    const disconnectWebSocket = () => {
      if (sttSocket.value) sttSocket.value.close(1000, 'User disconnected');
      if (ttsSocket.value) ttsSocket.value.close(1000, 'User disconnected');
      stopVoiceChat();
      isSttConnected.value = false;
      isTtsConnected.value = false;
      addToLog('Disconnected all connections.');
    };

    const updateSttServerConfig = () => {
      if (!sttSocket.value || sttSocket.value.readyState !== WebSocket.OPEN) {
        addToLog('STT WebSocket not connected, cannot update config');
        return;
      }
      const params = { action: 'config', data: { user_token: userToken.value } };
      sttSocket.value.send(JSON.stringify(params));
      addToLog('STT session parameters updated (user token)');
    };

    const startVoiceChat = async () => {
      if (!isConnected.value || isRecording.value) return;

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
        addToLog('Recording started');
      } catch (error) {
        addToLog(`Failed to start recording: ${error.message}`, 'error');
      }
    };
    
    const processAudio = (e) => {
      if (!isRecording.value) return;

      const inputData = e.inputBuffer.getChannelData(0);
      const rms = Math.sqrt(inputData.reduce((sum, val) => sum + val * val, 0) / inputData.length);
      const isSpeechDetected = rms > AUDIO_CONFIG.AUDIO_RMS_THRESHOLD;

      const audioData = new Int16Array(inputData.map(n => Math.max(-32768, Math.min(32767, n * 32768))));

      if (isSpeechDetected) {
        if (!isClientSpeaking.value) isClientSpeaking.value = true;
        speechFrames.value.push(audioData);
        silenceFrames.value = 0;
      } else if (isClientSpeaking.value) {
        silenceFrames.value++;
        if (silenceFrames.value <= AUDIO_CONFIG.SPEECH_PADDING_FRAMES) {
          speechFrames.value.push(audioData);
        }
        if (silenceFrames.value >= AUDIO_CONFIG.MAX_SILENCE_FRAMES) {
          if (speechFrames.value.length > 0) {
            sendAudioToServer(concatenateAudioChunks(speechFrames.value));
          }
          isClientSpeaking.value = false;
          speechFrames.value = [];
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
      const message = { action: "audio", data: { audio_data: base64Audio, format: "pcm" } };
      sttSocket.value.send(JSON.stringify(message));
    };

    const stopVoiceChat = () => {
      if (!isRecording.value) return;

      isRecording.value = false;
      isClientSpeaking.value = false;
      
      if (audioProcessor.value) audioProcessor.value.disconnect();
      if (audioContext.value) audioContext.value.close();
      if (mediaStream.value) mediaStream.value.getTracks().forEach(track => track.stop());

      audioProcessor.value = null;
      audioContext.value = null;
      mediaStream.value = null;
      speechFrames.value = [];

      addToLog('Recording stopped');
    };

    const handleSttMessage = (event) => {
      lastServerActivity.value = Date.now();
      const message = JSON.parse(event.data);
      addToLog(`STT: ${JSON.stringify(message).substring(0, 150)}`);
      
      if (message.type === 'llm_response') {
         addMessageToConversation(message.data.text, 'assistant');
      } else if (message.type === 'recognition_result') {
         addMessageToConversation(message.text, 'user');
      }
    };

    const handleTtsMessage = (event) => {
      if (event.data === 'pong') return;
      try {
        const message = JSON.parse(event.data);
        if (message.type !== 'audio') return;
        addToLog(`TTS: Received audio for "${message.text.substring(0, 20)}..."`, 'success');
        const audioBlob = base64ToBlob(message.audio_base64, 'audio/wav');
        const audioUrl = URL.createObjectURL(audioBlob);
        audioQueue.value.push({ url: audioUrl, text: message.text, isBlob: true });
        if (!isPlaying.value) playNextAudio();
      } catch (e) {
        addToLog(`TTS: Failed to parse message: ${e.message}`, 'error');
      }
    };
    
    const base64ToBlob = (base64, mimeType) => {
      const byteChars = atob(base64);
      const byteNumbers = new Array(byteChars.length);
      for (let i = 0; i < byteChars.length; i++) byteNumbers[i] = byteChars.charCodeAt(i);
      return new Blob([new Uint8Array(byteNumbers)], { type: mimeType });
    };

    const addMessageToConversation = (text, sender) => {
      conversationHistory.value.push({ sender, text });
    };

    const onAudioEnded = () => {
      const finishedAudio = audioQueue.value[0];
      if (finishedAudio && finishedAudio.isBlob) URL.revokeObjectURL(finishedAudio.url);
      
      audioQueue.value.shift();
      isPlaying.value = false;
      currentAudio.value = null;
      isSpeaking.value = false;
      currentAudioUrl.value = '';

      if (audioQueue.value.length > 0) {
        setTimeout(() => playNextAudio(), 50);
      }
    };

    const onAudioError = (error) => {
      addToLog(`Audio playback error: ${error.message || 'Unknown error'}`, 'error');
      isPlaying.value = false;
      audioQueue.value.shift();
      currentAudio.value = null;
      playNextAudio();
    };

    const onAudioLoadStart = () => {};
    const onAudioCanPlay = () => {};

    const playNextAudio = () => {
      if (audioQueue.value.length === 0 || isPlaying.value) {
        if (audioQueue.value.length === 0) {
          isSpeaking.value = false;
          currentAudioUrl.value = '';
        }
        return;
      }
      
      currentAudio.value = audioQueue.value[0];
      isPlaying.value = true;
      isSpeaking.value = true; // For Live2D
      currentAudioUrl.value = currentAudio.value.url; // For Live2D
    };

    onMounted(() => {
      updateCanvasSize();
      window.addEventListener('resize', updateCanvasSize);

      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        addToLog('This browser does not support audio recording.', 'error');
        return;
      }
      // No automatic connection
    });
    
    onUnmounted(() => {
      window.removeEventListener('resize', updateCanvasSize);
      disconnectWebSocket();
      if (audioContext.value && audioContext.value.state !== 'closed') {
        audioContext.value.close();
      }
    });

    return {
      isSpeaking,
      currentAudioUrl,
      currentAudio,
      audioQueue,
      onAudioEnded,
      onAudioError,
      onAudioLoadStart,
      onAudioCanPlay,
      toggleConnection,
      isConnected,
      isConnecting,
      connectionButtonText,
      canvasSize,
    };
  }
};
</script>

<style scoped>
.live2d-container {
  position: relative;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
}

.controls {
  position: absolute;
  top: 20px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10;
}

.connect-btn {
  padding: 10px 20px;
  font-size: 16px;
  border-radius: 8px;
  cursor: pointer;
  background-color: #4CAF50;
  color: white;
  border: none;
  transition: background-color 0.3s;
}

.connect-btn:disabled {
  background-color: #cccccc;
  cursor: not-allowed;
}
</style> 