<template>
  <!-- 设置面板 -->
  <div class="settings-panel" :class="{ 'panel-hidden': isSettingsPanelHidden }" style="display: none;">
    <div class="panel-header" @click="toggleSettingsPanel">
      设置面板 <span>{{ isSettingsPanelHidden ? '展开' : '收起' }}</span>
    </div>
    
    <div class="panel-content" v-if="!isSettingsPanelHidden">
      <div class="control-section">
        <button class="primary-btn" @click="$emit('play-motion')">随机动作</button>
        <button class="primary-btn" @click="$emit('play-expression')">随机表情</button>
      </div>

      <div class="control-section">
        <label>数字人模型</label>
        <select v-model="selectedModelValue" class="select-input">
          <option v-for="model in modelList" :key="model" :value="model">{{ model }}</option>
        </select>
        <button class="primary-btn" @click="$emit('update-model', selectedModelValue)" :disabled="isProcessing">更新模型</button>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'Live2dSettings',
  props: {
    modelList: {
      type: Array,
      required: true
    },
    selectedModel: {
      type: String,
      required: true
    },
    isProcessing: {
      type: Boolean,
      default: false
    },
    isPanelHidden: {
      type: Boolean,
      default: false
    }
  },
  
  data() {
    return {
      isSettingsPanelHidden: this.isPanelHidden,
      selectedModelValue: this.selectedModel
    }
  },
  
  watch: {
    isPanelHidden(newVal) {
      this.isSettingsPanelHidden = newVal;
    },
    selectedModel(newVal) {
      this.selectedModelValue = newVal;
    },
    isSettingsPanelHidden(newVal) {
      this.$emit('panel-state-change', newVal);
    },
    selectedModelValue(newVal) {
      this.$emit('model-selection-change', newVal);
    }
  },
  
  methods: {
    toggleSettingsPanel() {
      this.isSettingsPanelHidden = !this.isSettingsPanelHidden;
    }
  }
}
</script>

<style scoped>
/* 设置面板样式 */
.settings-panel {
  position: fixed;
  left: 20px;
  bottom: 20px;
  z-index: 1000;
  background-color: rgba(255, 255, 255, 0.9);
  border-radius: 10px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  width: 260px;
  max-width: 90vw;
  transition: all 0.3s ease;
  overflow: hidden;
  border: 1px solid rgba(200, 200, 200, 0.5);
}

.panel-header {
  padding: 10px 15px;
  background-color: rgba(66, 185, 131, 0.9);
  color: white;
  cursor: pointer;
  font-weight: bold;
  display: flex;
  justify-content: space-between;
}

.panel-content {
  padding: 15px;
  max-height: 350px;
  overflow-y: auto;
}

.panel-hidden .panel-content {
  display: none;
}

.control-section {
  margin-bottom: 15px;
}

/* 按钮样式 */
.primary-btn {
  background-color: #42b983;
  color: white;
  border: none;
  border-radius: 4px;
  padding: 6px 12px;
  cursor: pointer;
  font-size: 14px;
  margin-right: 8px;
  margin-bottom: 8px;
}

.primary-btn:disabled {
  background-color: #a8d5c2;
  cursor: not-allowed;
}

/* 下拉菜单样式 */
.select-input {
  padding: 6px;
  border-radius: 4px;
  border: 1px solid #ccc;
  margin-bottom: 10px;
  width: 100%;
}
</style>
