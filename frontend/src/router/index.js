import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '@/views/HomeView.vue'
import Assistant from '@/views/AssistantView/index.vue'
import test from '@/views/testView.vue'
import Live2dView from '@/views/Live2dView/index.vue'
import VoiceAssistantLive2d from '@/views/VoiceAssistantLive2d/index.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView
    },
    {
      path: '/test',
      name: 'test',
      component: test,
      meta: {
        title: '测试页面'
      }
    },
    {
      path: '/live2d',
      name: 'live2d',
      component: Live2dView
    },
    {
      path: '/voice-assistant-live2d',
      name: 'VoiceAssistantLive2d',
      component: VoiceAssistantLive2d,
      meta: {
        title: 'Live2D 语音助手'
      }
    },
    {
      path: '/assistant',
      name: 'Assistant',
      component: Assistant,
      meta: {
        title: '助手页面'
      }
    }
  ]
})

// 全局路由守卫
router.beforeEach((to, from, next) => {
  next()
})

export default router
