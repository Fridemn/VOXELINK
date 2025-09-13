<template>
    <div>
        1111
    </div>
  <div class="test-container">
    <div class="test-card">
      <h2 class="test-title">测试页面</h2>
      <div class="test-content">
        <div class="notice">
          用户注册和验证码功能已被移除
        </div>
        <button
          @click="handleTest"
          class="test-button"
        >
          测试按钮
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const handleTest = () => {
  alert('这是一个测试页面，用户相关功能已被移除')
}
</script>

<style lang="scss" scoped>
.test-container {
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: #f3f4f6;
  padding: 20px;
}

.test-card {
  background-color: white;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  width: 100%;
  max-width: 400px;
}

.test-title {
  font-size: 24px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 20px;
  text-align: center;
}

.test-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.notice {
  padding: 12px;
  background-color: #fef3c7;
  border: 1px solid #f59e0b;
  border-radius: 6px;
  color: #92400e;
  text-align: center;
}

.test-button {
  padding: 12px 24px;
  background-color: #2563eb;
  color: white;
  border-radius: 6px;
  font-weight: 500;
  transition: all 0.2s;

  &:hover {
    background-color: #1d4ed8;
  }
}
</style>
