<template>
  <div class="min-h-screen bg-gray-100 flex flex-col items-center justify-center">
    <div class="text-4xl font-bold text-gray-800 mb-8">
      欢迎来到首页
    </div>

    <router-link 
      to="/login" 
      class="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors duration-200 shadow-md hover:shadow-lg"
    >
      登录/注册
    </router-link>
  </div>
</template>

<script setup>
</script>

<style lang="scss" scoped>
// 如果有特定的scss样式可以保留，但使用Tailwind后大部分样式可以直接在template中实现
</style>
