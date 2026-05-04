<script setup>
import { ref } from 'vue'
import { useDownload } from '../composables/useDownload'
import { formatFileSize, formatDuration } from '../api'

const {
  url, loading, error, videoInfo, selectedFormat,
  status, progress, speed, downloaded, total, eta, fileUrl,
  canParse, canDownload, isDone, isDownloading,
  parse, download, reset,
} = useDownload()

const menuOpen = ref(false)

function handleKeydown(e) {
  if (e.key === 'Enter' && canParse.value && !loading.value) {
    parse()
  }
}

function handlePaste(e) {
  const text = e.clipboardData?.getData('text')
  if (text) {
    setTimeout(() => {
      if (canParse.value && !loading.value) parse()
    }, 100)
  }
}
</script>

<template>
  <div class="min-h-screen bg-white flex flex-col font-sans">

    <!-- ═══ Navbar ═══ -->
    <nav class="sticky top-0 z-50 glass-card">
      <div class="max-w-[980px] mx-auto px-6 h-11 flex items-center justify-between">
        <!-- Logo -->
        <router-link to="/" class="flex items-center gap-2 group">
          <div class="w-7 h-7 bg-[#0071e3] rounded-lg flex items-center justify-center
                      group-hover:bg-[#0077ed] transition-colors">
            <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" stroke-width="2.2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round"
                    d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
            </svg>
          </div>
          <span class="font-semibold text-[#1d1d1f] text-sm tracking-tight">万能下载</span>
        </router-link>

        <!-- Desktop Links -->
        <div class="hidden md:flex items-center gap-7 text-xs text-[#86868b]">
          <a href="#features" class="hover:text-[#1d1d1f] transition-colors">功能</a>
          <a href="#platforms" class="hover:text-[#1d1d1f] transition-colors">支持平台</a>
          <a href="#pricing" class="hover:text-[#1d1d1f] transition-colors">定价</a>
        </div>

        <!-- Mobile Menu Button -->
        <button @click="menuOpen = !menuOpen" class="md:hidden p-2 -mr-2 text-[#1d1d1f]">
          <svg v-if="!menuOpen" class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
            <path stroke-linecap="round" d="M4 6h16M4 12h16M4 18h16"/>
          </svg>
          <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
            <path stroke-linecap="round" d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>
      </div>

      <!-- Mobile Menu -->
      <div v-if="menuOpen" class="md:hidden border-t border-gray-100 px-6 py-4 space-y-3 text-sm text-[#1d1d1f]">
        <a href="#features" @click="menuOpen = false" class="block py-1">功能</a>
        <a href="#platforms" @click="menuOpen = false" class="block py-1">支持平台</a>
        <a href="#pricing" @click="menuOpen = false" class="block py-1">定价</a>
      </div>
    </nav>

    <!-- ═══ Hero Section ═══ -->
    <section class="hero-mesh pt-16 md:pt-24 pb-12 md:pb-16 px-6 text-center">
      <div class="max-w-[980px] mx-auto">
        <!-- Headline -->
        <h1 class="animate-fade-in-up text-[#1d1d1f] text-[clamp(2.25rem,6vw,3.5rem)] font-semibold tracking-tight leading-[1.1] mb-4">
          下载任何视频<br class="hidden sm:inline" />
          <span class="gradient-text">只需一个链接</span>
        </h1>

        <!-- Subtitle -->
        <p class="animate-fade-in-up-delay-1 text-[#86868b] text-base md:text-xl mb-10 md:mb-12 max-w-lg mx-auto leading-relaxed">
          支持 YouTube、Bilibili、抖音、Twitter 等 1000+ 平台<br class="hidden sm:inline" />
          手机也能用，随时随地下载
        </p>

        <!-- Input Area -->
        <div class="animate-fade-in-up-delay-2 max-w-2xl mx-auto">
          <div class="relative flex gap-2 md:gap-3">
            <div class="flex-1 relative">
              <input
                v-model="url"
                @keydown="handleKeydown"
                @paste="handlePaste"
                type="url"
                placeholder="在这里粘贴视频链接..."
                class="w-full pl-4 pr-4 md:pl-5 md:pr-5 py-3 md:py-4 rounded-2xl bg-white text-[#1d1d1f] text-sm md:text-base
                       border border-gray-200 shadow-sm
                       focus:outline-none focus:border-[#0071e3] input-glow
                       placeholder:text-[#c7c7cc] transition-all"
              />
              <!-- Paste hint icon -->
              <div v-if="!url" class="absolute right-4 top-1/2 -translate-y-1/2 hidden md:flex items-center gap-1.5 text-[#c7c7cc]">
                <kbd class="px-1.5 py-0.5 text-[10px] bg-gray-50 rounded border border-gray-200">Ctrl</kbd>
                <span class="text-[10px]">+</span>
                <kbd class="px-1.5 py-0.5 text-[10px] bg-gray-50 rounded border border-gray-200">V</kbd>
              </div>
            </div>
            <button
              @click="parse"
              :disabled="!canParse || loading"
              class="px-5 md:px-8 py-3 md:py-4 bg-[#0071e3] text-white font-medium rounded-2xl text-sm md:text-base
                     hover:bg-[#0077ed] active:bg-[#0071e3] active:scale-[0.98]
                     disabled:opacity-30 disabled:cursor-not-allowed disabled:active:scale-100
                     transition-all whitespace-nowrap shadow-sm"
            >
              <span v-if="loading" class="flex items-center gap-2">
                <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                </svg>
                解析中
              </span>
              <span v-else>解析视频</span>
            </button>
          </div>

          <!-- Error -->
          <transition name="fade">
            <p v-if="error" class="mt-3 text-red-500 text-sm flex items-center justify-center gap-1.5">
              <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
              </svg>
              {{ error }}
            </p>
          </transition>
        </div>
      </div>
    </section>

    <!-- ═══ Video Result Card ═══ -->
    <transition name="slide">
      <section v-if="videoInfo" class="max-w-2xl mx-auto w-full px-6 pb-12">
        <div class="animate-scale-in bg-white rounded-3xl shadow-lg border border-gray-100 overflow-hidden">
          <!-- Video Info Header -->
          <div class="p-5 md:p-6 flex gap-4">
            <div v-if="videoInfo.thumbnail" class="relative flex-shrink-0">
              <img
                :src="videoInfo.thumbnail"
                alt=""
                class="w-32 md:w-44 h-20 md:h-[104px] object-cover rounded-xl bg-gray-100"
                @error="($event.target).style.display = 'none'"
              />
              <!-- Duration badge -->
              <div v-if="videoInfo.duration" class="absolute bottom-1.5 right-1.5 bg-black/70 text-white text-[10px] px-1.5 py-0.5 rounded-md">
                {{ formatDuration(videoInfo.duration) }}
              </div>
            </div>
            <div class="min-w-0 flex-1">
              <h3 class="text-[#1d1d1f] font-semibold text-base md:text-lg leading-snug mb-1.5 line-clamp-2">
                {{ videoInfo.title }}
              </h3>
              <div class="flex flex-wrap items-center gap-x-2 gap-y-1 text-[#86868b] text-xs md:text-sm">
                <span v-if="videoInfo.author">{{ videoInfo.author }}</span>
                <span v-if="videoInfo.platform"
                      class="inline-flex items-center px-2 py-0.5 bg-[#f5f5f7] rounded-full text-[10px] font-medium text-[#86868b] uppercase tracking-wide">
                  {{ videoInfo.platform }}
                </span>
              </div>
            </div>
          </div>

          <!-- Divider -->
          <div class="h-px bg-gray-100 mx-5 md:mx-6"></div>

          <!-- Quality Selector -->
          <div class="p-5 md:p-6">
            <label class="text-xs font-medium text-[#86868b] uppercase tracking-wider mb-3 block">选择清晰度</label>
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <button
                v-for="fmt in videoInfo.formats"
                :key="fmt.format_id"
                @click="selectedFormat = fmt.format_id"
                :class="[
                  'px-3 py-3 rounded-xl text-sm font-medium transition-all text-center',
                  selectedFormat === fmt.format_id
                    ? 'bg-[#0071e3] text-white shadow-sm shadow-blue-200'
                    : 'bg-[#f5f5f7] text-[#1d1d1f] hover:bg-[#e8e8ed] active:scale-[0.97]'
                ]"
              >
                <div>{{ fmt.resolution }}</div>
                <div v-if="fmt.filesize" class="text-[10px] mt-0.5 opacity-60">
                  {{ formatFileSize(fmt.filesize) }}
                </div>
              </button>
            </div>
          </div>

          <!-- Download Button -->
          <div class="px-5 md:px-6 pb-5 md:pb-6">
            <button
              v-if="!isDone && !isDownloading"
              @click="download"
              :disabled="!canDownload"
              class="w-full py-4 bg-[#0071e3] text-white font-semibold rounded-2xl text-base
                     hover:bg-[#0077ed] active:bg-[#0071e3] active:scale-[0.99]
                     disabled:opacity-30 disabled:cursor-not-allowed
                     transition-all shadow-sm"
            >
              开始下载
            </button>

            <!-- Progress -->
            <div v-if="isDownloading" class="space-y-4">
              <!-- Progress Bar -->
              <div class="relative h-2 bg-[#f5f5f7] rounded-full overflow-hidden">
                <div
                  class="absolute inset-y-0 left-0 bg-[#0071e3] rounded-full transition-all duration-700 ease-out progress-glow"
                  :style="{ width: `${progress}%` }"
                />
              </div>

              <!-- Stats Row -->
              <div class="flex justify-between items-center text-sm">
                <span class="text-[#1d1d1f] font-semibold tabular-nums">{{ progress }}%</span>
                <div class="flex items-center gap-3 text-[#86868b] text-xs">
                  <span v-if="speed">{{ speed }}</span>
                  <span v-if="total">{{ formatFileSize(downloaded) }} / {{ formatFileSize(total) }}</span>
                  <span v-if="eta">剩余 {{ eta }}s</span>
                </div>
              </div>

              <!-- Status Text -->
              <p class="text-center text-sm text-[#86868b] flex items-center justify-center gap-2">
                <svg v-if="status === 'merging'" class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                </svg>
                {{ status === 'merging' ? '正在合并音视频...' : '下载中...' }}
              </p>
            </div>

            <!-- Done -->
            <div v-if="isDone" class="text-center space-y-4">
              <div class="w-12 h-12 mx-auto bg-green-50 rounded-full flex items-center justify-center">
                <svg class="w-6 h-6 text-green-500" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>
                </svg>
              </div>
              <div>
                <p class="text-[#1d1d1f] font-semibold mb-1">下载完成</p>
                <p class="text-[#86868b] text-sm">视频已准备好，点击保存到本地</p>
              </div>
              <a
                :href="fileUrl"
                download
                class="inline-flex items-center gap-2 px-8 py-4 bg-[#0071e3] text-white font-semibold rounded-2xl
                       hover:bg-[#0077ed] active:scale-[0.98] transition-all text-base shadow-sm"
              >
                <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round"
                        d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                </svg>
                保存到本地
              </a>
              <div>
                <button
                  @click="reset"
                  class="text-sm text-[#0071e3] hover:underline"
                >
                  继续下载其他视频
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </transition>

    <!-- ═══ Features Section ═══ -->
    <section v-if="!videoInfo" id="features" class="bg-[#f5f5f7] py-16 md:py-24 px-6">
      <div class="max-w-[980px] mx-auto">
        <h2 class="text-center text-[#1d1d1f] text-2xl md:text-[32px] font-semibold tracking-tight mb-4">
          为什么选择万能下载
        </h2>
        <p class="text-center text-[#86868b] text-base md:text-lg mb-12 md:mb-16 max-w-md mx-auto">
          简单、快速、支持所有平台
        </p>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-5">
          <!-- Feature 1 -->
          <div class="card-hover bg-white rounded-3xl p-7 md:p-8 text-center">
            <div class="w-12 h-12 mx-auto mb-5 bg-blue-50 rounded-2xl flex items-center justify-center">
              <svg class="w-6 h-6 text-[#0071e3]" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round"
                      d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9"/>
              </svg>
            </div>
            <h3 class="text-[#1d1d1f] font-semibold text-lg mb-2">1000+ 平台</h3>
            <p class="text-[#86868b] text-sm leading-relaxed">
              YouTube、Bilibili、抖音、Twitter、Instagram 等全球主流视频平台全覆盖
            </p>
          </div>

          <!-- Feature 2 -->
          <div class="card-hover bg-white rounded-3xl p-7 md:p-8 text-center">
            <div class="w-12 h-12 mx-auto mb-5 bg-purple-50 rounded-2xl flex items-center justify-center">
              <svg class="w-6 h-6 text-[#5856d6]" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round"
                      d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"/>
              </svg>
            </div>
            <h3 class="text-[#1d1d1f] font-semibold text-lg mb-2">高清下载</h3>
            <p class="text-[#86868b] text-sm leading-relaxed">
              支持 360p 到 4K 多种清晰度，音视频完整，自由选择你想要的画质
            </p>
          </div>

          <!-- Feature 3 -->
          <div class="card-hover bg-white rounded-3xl p-7 md:p-8 text-center">
            <div class="w-12 h-12 mx-auto mb-5 bg-orange-50 rounded-2xl flex items-center justify-center">
              <svg class="w-6 h-6 text-[#ff9500]" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round"
                      d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z"/>
              </svg>
            </div>
            <h3 class="text-[#1d1d1f] font-semibold text-lg mb-2">手机也能用</h3>
            <p class="text-[#86868b] text-sm leading-relaxed">
              无需安装 App，手机浏览器直接访问，随时随地下载你喜欢的视频
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- ═══ Platforms Section ═══ -->
    <section v-if="!videoInfo" id="platforms" class="py-16 md:py-24 px-6">
      <div class="max-w-[980px] mx-auto text-center">
        <h2 class="text-[#1d1d1f] text-2xl md:text-[32px] font-semibold tracking-tight mb-4">
          支持各大平台
        </h2>
        <p class="text-[#86868b] text-base md:text-lg mb-12">
          持续更新，覆盖全球主流视频平台
        </p>

        <div class="flex flex-wrap justify-center gap-2 md:gap-3 max-w-xl mx-auto">
          <span v-for="p in ['YouTube', 'Bilibili', '抖音', 'Twitter/X', 'Instagram',
                             '微博', '小红书', '快手', 'Facebook', 'TikTok',
                             'Vimeo', 'Pinterest']"
                :key="p"
                class="platform-tag px-4 py-2 bg-[#f5f5f7] rounded-full text-sm text-[#1d1d1f] font-medium cursor-default select-none"
          >
            {{ p }}
          </span>
          <span class="platform-tag px-4 py-2 bg-[#0071e3]/5 text-[#0071e3] rounded-full text-sm font-medium cursor-default">
            1000+ 更多
          </span>
        </div>
      </div>
    </section>

    <!-- ═══ Pricing Section ═══ -->
    <section v-if="!videoInfo" id="pricing" class="bg-[#f5f5f7] py-16 md:py-24 px-6">
      <div class="max-w-[980px] mx-auto text-center">
        <h2 class="text-[#1d1d1f] text-2xl md:text-[32px] font-semibold tracking-tight mb-4">
          选择适合你的方案
        </h2>
        <p class="text-[#86868b] text-base md:text-lg mb-12">
          免费开始，按需升级
        </p>

        <div class="grid grid-cols-1 md:grid-cols-2 max-w-2xl mx-auto gap-5">
          <!-- Free -->
          <div class="bg-white rounded-3xl p-7 md:p-8 text-left border border-gray-100">
            <div class="text-xs font-medium text-[#86868b] uppercase tracking-wider mb-3">免费版</div>
            <div class="flex items-baseline gap-1 mb-5">
              <span class="text-[#1d1d1f] text-4xl font-semibold">¥0</span>
              <span class="text-[#86868b] text-sm">/永久</span>
            </div>
            <ul class="space-y-3 mb-7 text-sm text-[#1d1d1f]">
              <li class="flex items-center gap-2.5">
                <svg class="w-4 h-4 text-[#86868b] flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
                </svg>
                标清视频下载 (≤720p)
              </li>
              <li class="flex items-center gap-2.5">
                <svg class="w-4 h-4 text-[#86868b] flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
                </svg>
                单个视频下载
              </li>
              <li class="flex items-center gap-2.5">
                <svg class="w-4 h-4 text-[#86868b] flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
                </svg>
                全平台支持
              </li>
            </ul>
            <button class="w-full py-3 rounded-2xl border border-[#0071e3] text-[#0071e3] font-medium text-sm
                           hover:bg-[#0071e3]/5 active:bg-[#0071e3]/10 transition-all">
              免费使用
            </button>
          </div>

          <!-- Pro -->
          <div class="relative bg-[#1d1d1f] rounded-3xl p-7 md:p-8 text-left">
            <div class="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 bg-[#0071e3] text-white text-[10px] font-semibold rounded-full uppercase tracking-wider">
              推荐
            </div>
            <div class="text-xs font-medium text-[#86868b] uppercase tracking-wider mb-3">Pro 版</div>
            <div class="flex items-baseline gap-1 mb-5">
              <span class="text-white text-4xl font-semibold">¥29</span>
              <span class="text-[#86868b] text-sm">/月</span>
            </div>
            <ul class="space-y-3 mb-7 text-sm text-white/90">
              <li class="flex items-center gap-2.5">
                <svg class="w-4 h-4 text-[#0071e3] flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
                </svg>
                4K 高清视频下载
              </li>
              <li class="flex items-center gap-2.5">
                <svg class="w-4 h-4 text-[#0071e3] flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
                </svg>
                批量下载 / 播放列表
              </li>
              <li class="flex items-center gap-2.5">
                <svg class="w-4 h-4 text-[#0071e3] flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
                </svg>
                字幕下载 & 翻译
              </li>
              <li class="flex items-center gap-2.5">
                <svg class="w-4 h-4 text-[#0071e3] flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
                </svg>
                AI 视频总结
              </li>
            </ul>
            <button class="w-full py-3 rounded-2xl bg-[#0071e3] text-white font-medium text-sm
                           hover:bg-[#0077ed] active:scale-[0.98] transition-all">
              立即订阅
            </button>
          </div>
        </div>
      </div>
    </section>

    <!-- ═══ Footer ═══ -->
    <footer class="border-t border-gray-200 bg-[#f5f5f7]">
      <div class="max-w-[980px] mx-auto px-6 py-6">
        <div class="flex flex-col md:flex-row justify-between items-center gap-3">
          <p class="text-xs text-[#86868b]">仅供个人学习使用，请勿用于商业用途</p>
          <div class="flex items-center gap-5 text-xs text-[#86868b]">
            <a href="#" class="hover:text-[#1d1d1f] transition-colors">关于</a>
            <a href="#" class="hover:text-[#1d1d1f] transition-colors">隐私</a>
            <a href="#" class="hover:text-[#1d1d1f] transition-colors">联系</a>
          </div>
        </div>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.3s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.slide-enter-active { transition: all 0.5s cubic-bezier(0.25, 0.46, 0.45, 0.94); }
.slide-leave-active { transition: all 0.3s ease; }
.slide-enter-from { opacity: 0; transform: translateY(20px); }
.slide-leave-to { opacity: 0; transform: translateY(-10px); }
</style>
