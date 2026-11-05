<template>
  <!-- 页面外壳导航栏：历史记录列表页与详情页共用，右侧链接由调用方传入。
       首页的导航栏结构不同（锚点链接 + 移动端汉堡菜单），仍留在 Home.vue 里。 -->
  <nav class="sticky top-0 z-50 glass-card">
    <div class="max-w-[1200px] mx-auto px-6 h-11 flex items-center justify-between">
      <router-link to="/" class="flex items-center gap-2 group">
        <div class="w-7 h-7 bg-[#0071e3] rounded-lg flex items-center justify-center
                    group-hover:bg-[#0077ed] transition-colors">
          <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" stroke-width="2.2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round"
                  d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
          </svg>
        </div>
        <span class="font-semibold text-[#1d1d1f] text-sm tracking-tight">时雨视频分析</span>
      </router-link>

      <div class="flex items-center gap-7 text-xs text-[#86868b]">
        <slot />
      </div>
    </div>
  </nav>
</template>

<script setup>
// 纯展示组件：导航栏的骨架固定，右侧链接交给插槽，调用方按页面需要放内容
</script>
