<template>
  <div class="card">
    <h2 class="text-xl font-semibold text-center text-gray-700 mb-4">日志</h2>
    <div id="log" class="max-h-52 overflow-y-auto p-3 bg-gray-100 border border-gray-200 rounded-md font-mono text-xs">
      <div v-for="(logEntry, index) in logs" :key="index" class="mb-1">
        {{ logEntry }}
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'LogPanel',
  props: {
    logs: {
      type: Array,
      default: () => []
    }
  }
};
</script>

<style scoped>
/* 使用Tailwind替代了这些自定义样式 */
</style>
