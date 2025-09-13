<template>
  <div class="card">
    <h2 class="text-xl font-semibold text-center text-gray-700 mb-4">对话历史</h2>
    <div id="conversation" class="h-80 overflow-y-auto p-3 bg-gray-50 border border-gray-200 rounded-md">
      <div 
        v-for="(message, index) in conversationHistory" 
        :key="index" 
        :class="[
          message.sender === 'user' ? 
            'bg-blue-100 ml-[20%] text-right' : 
            'bg-gray-100 mr-[20%] text-left',
          'p-3 my-2 rounded-lg',
          message.className === 'assistant-response-building' ? 'border border-gray-300 bg-gray-50' : ''
        ]"
      >
        {{ message.text }}
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ConversationHistory',
  props: {
    conversationHistory: {
      type: Array,
      default: () => []
    }
  }
};
</script>

<style scoped>
/* 使用Tailwind替代了这些自定义样式 */
</style>
