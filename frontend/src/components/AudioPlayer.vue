<template>
  <div class="audio-player">
    <audio 
      ref="audioElement"
      controls 
      class="w-full rounded" 
      :key="src"
      @error="handleError"
      @loadeddata="handleLoaded"

    >
      <source 
        :src="src" 
        :type="audioType"
      >
      您的浏览器不支持音频播放
    </audio>
    <div v-if="loading" class="text-xs text-gray-400 mt-1">
      加载音频中...
    </div>
    <div v-if="error" class="text-xs text-red-500 mt-1">
      {{ error }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue';

const props = defineProps({
  src: {
    type: String,
    required: true
  },
  mimeType: {
    type: String,
    default: ''
  },
  autoPlay: {
    type: Boolean,
    default: false
  }
});

const audioElement = ref(null);
const loading = ref(true);
const error = ref('');

// 根据URL或传入的mimeType确定音频类型
const audioType = computed(() => {
  if (props.mimeType) return props.mimeType;
  
  const url = props.src;
  if (!url) return 'audio/mpeg';
  if (url.endsWith('.mp3')) return 'audio/mpeg';
  if (url.endsWith('.wav')) return 'audio/wav';
  if (url.endsWith('.ogg')) return 'audio/ogg';
  return 'audio/mpeg'; // 默认类型
});

// 处理音频加载错误
const handleError = (e) => {
  console.error('音频加载失败:', e);
  error.value = '音频加载失败，请刷新重试';
  loading.value = false;
};

// 音频加载完成
const handleLoaded = () => {
  loading.value = false;
  if (props.autoPlay && audioElement.value) {
    audioElement.value.play().catch(err => {
      console.warn('自动播放失败，可能需要用户交互:', err);
    });
  }
};

// 监听src变化
watch(() => props.src, () => {
  if (props.src) {
    loading.value = true;
    error.value = '';
  }
});

// 组件挂载时
onMounted(() => {
  if (!props.src) {
    loading.value = false;
  }
});
</script>

<style scoped>
.audio-player {
  width: 100%;
}
</style>
