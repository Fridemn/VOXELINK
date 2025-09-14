<template>
  <div class="card">
    <h2 class="text-xl font-semibold text-center text-gray-700 mb-4">TTS设置</h2>
    <div class="config-panel">
      <div class="config-row">
        <label for="provider" class="text-gray-700">TTS提供者:</label>
        <select id="provider" :value="provider" @change="$emit('update:provider', $event.target.value)"
                class="flex-1">
          <option value="tts">GSVI</option>
          <option value="azure">Azure</option>
          <option value="elevenlabs">ElevenLabs</option>
        </select>
      </div>
      <div class="config-row">
        <label for="api-base" class="text-gray-700">API基础URL:</label>
        <input type="text" id="api-base" :value="apiBase" @change="$emit('update:api-base', $event.target.value)" 
               class="flex-1" />
      </div>
      <div class="config-row">
        <label for="character" class="text-gray-700">角色名称(可选):</label>
        <input type="text" id="character" :value="character" placeholder="角色名称" 
               @change="$emit('update:character', $event.target.value)" 
               class="flex-1" />
      </div>
      <div class="config-row">
        <label for="emotion" class="text-gray-700">情感(可选):</label>
        <input type="text" id="emotion" :value="emotion" placeholder="情感" 
               @change="$emit('update:emotion', $event.target.value)" 
               class="flex-1" />
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'TTSSettings',
  props: {
    provider: {
      type: String,
      default: 'tts'
    },
    apiBase: {
      type: String,
      default: 'http://115.25.45.126:5000'
    },
    character: {
      type: String,
      default: 'Paimeng'
    },
    emotion: {
      type: String,
      default: 'default'
    }
  },
  emits: ['update:provider', 'update:api-base', 'update:character', 'update:emotion']
};
</script>
