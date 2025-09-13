<template>
  <div class="card">
    <h2 class="text-xl font-semibold text-center text-gray-700 mb-4">语音助手配置</h2>
    <div class="config-panel">
      <div class="config-row">
        <label for="model" class="text-gray-700">LLM模型:</label>
        <select id="model" :value="selectedModel" @change="$emit('update:selected-model', $event.target.value)"
                class="flex-1">
          <option v-for="model in availableModels" :key="model" :value="model">
            {{ model }}
          </option>
        </select>
      </div>
      <div class="config-row">
        <label for="history-id" class="text-gray-700">对话历史ID:</label>
        <input type="text" id="history-id" :value="historyId" @change="$emit('update:history-id', $event.target.value)" 
               class="flex-1" />
        <button id="create-history-btn" class="neutral ml-3" @click="$emit('create-new-history')" 
                :disabled="createHistoryBtnDisabled">创建新对话</button>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'AssistantConfig',
  props: {
    historyId: {
      type: String,
      default: 'f40f30a3-b9d1-4c2b-b0db-b755f6373231'
    },
    selectedModel: {
      type: String,
      default: ''
    },
    availableModels: {
      type: Array,
      default: () => []
    },
    createHistoryBtnDisabled: {
      type: Boolean,
      default: true
    }
  },
  emits: ['update:history-id', 'update:selected-model', 'create-new-history'],
  mounted() {
    // 确保historyId有值，如果为空则使用默认值
    if (!this.historyId) {
      this.$emit('update:history-id', 'f40f30a3-b9d1-4c2b-b0db-b755f6373231');
    }
  }
};
</script>
