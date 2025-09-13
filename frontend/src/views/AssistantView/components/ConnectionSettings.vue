<template>
  <div class="card">
    <h2 class="text-xl font-semibold text-center text-gray-700 mb-4">连接设置</h2>
    <div class="config-row">
      <label for="api-url" class="text-gray-700">WebSocket API地址:</label>
      <input type="text" id="api-url" :value="apiUrl" @input="$emit('update:api-url', $event.target.value)" 
             class="flex-1" />
    </div>
    <div class="btn-group">
      <button id="connectBtn" class="neutral" @click="$emit('connect')" :disabled="connectBtnDisabled">连接服务器</button>
      <button id="disconnectBtn" class="secondary" @click="$emit('disconnect')" :disabled="disconnectBtnDisabled">断开连接</button>
    </div>
    <div id="connection-status" class="status" :class="connectionStatusClass">{{ connectionStatusText }}</div>
  </div>
</template>

<script>
export default {
  name: 'ConnectionSettings',
  props: {
    apiUrl: {
      type: String,
      required: true
    },
    isConnected: {
      type: Boolean,
      default: false
    },
    connectionStatusText: {
      type: String,
      default: '未连接'
    },
    connectionStatusClass: {
      type: String,
      default: 'disconnected'
    },
    connectBtnDisabled: {
      type: Boolean,
      default: false
    },
    disconnectBtnDisabled: {
      type: Boolean,
      default: true
    }
  },
  emits: ['connect', 'disconnect', 'update:api-url']
};
</script>
