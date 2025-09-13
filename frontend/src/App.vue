<script setup>
import { RouterLink, RouterView } from 'vue-router'
import { ref, provide, computed } from 'vue'
import { useRoute } from 'vue-router'
import Live2dView from '@/views/Live2dView/index.vue'

// 使用路由对象来监听路由变化
const route = useRoute()

// 控制Live2D显示状态
const showLive2D = ref(false)
const live2DSpeaking = ref(false)
const currentAudioUrl = ref('')

// 确定当前页面是否应该显示Live2D按钮
const shouldShowLive2DButton = computed(() => {
  return route.path === '/chat' || route.path === '/assistant'
})

// 控制Live2D显示/隐藏
const toggleLive2D = () => {
  showLive2D.value = !showLive2D.value
  
  // 如果关闭Live2D，确保停止说话
  if (!showLive2D.value && live2DSpeaking.value) {
    live2DSpeaking.value = false
    currentAudioUrl.value = ''
  }
  
  // 保存用户偏好
  localStorage.setItem('live2d_visible', showLive2D.value)
}

// 提供全局的Live2D控制方法给子组件使用
provide('live2dControls', {
  speak: (audioUrl) => {
    console.log('App.vue - Live2D开始说话:', audioUrl)
    // 确保有效的URL
    if (audioUrl && typeof audioUrl === 'string') {
      live2DSpeaking.value = true
      currentAudioUrl.value = audioUrl
    } else {
      console.warn('无效的音频URL:', audioUrl)
    }
  },
  stopSpeaking: () => {
    console.log('App.vue - Live2D停止说话')
    live2DSpeaking.value = false
    currentAudioUrl.value = ''
  },
  isVisible: showLive2D,
  isSpeaking: live2DSpeaking,
  audioUrl: currentAudioUrl,
  toggle: toggleLive2D
})

// 读取用户偏好
const initLive2DPreferences = () => {
  const savedVisibility = localStorage.getItem('live2d_visible')
  if (savedVisibility !== null) {
    showLive2D.value = savedVisibility === 'true'
  }
}

// 组件挂载时初始化
initLive2DPreferences()
</script>

<template>
  <div class="app-container">
    <!-- 原来的router-view保持不变 -->
    <router-view></router-view>
    
    <!-- 控制按钮 - 支持assistant页面 -->
    <button 
      v-if="shouldShowLive2DButton" 
      class="toggle-live2d-button" 
      @click="toggleLive2D"
    >
      {{ showLive2D ? '隐藏助手' : '显示助手' }}
    </button>
    
    <!-- Live2D悬浮界面 -->
    <Live2dView 
      v-if="showLive2D" 
      :speaking="live2DSpeaking" 
      :audioUrl="currentAudioUrl" 
    />
  </div>
</template>

<style scoped>
.toggle-live2d-button {
  position: fixed;
  bottom: 20px;
  right: 20px;
  z-index: 100;
  padding: 10px 15px;
  background-color: #42b983;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
}

.toggle-live2d-button:hover {
  background-color: #3aa876;
}
</style>
