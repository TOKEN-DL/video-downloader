<script setup>
import { useDownload } from '../composables/useDownload'
import { formatFileSize, formatDuration } from '../api'

const {
  url, loading, error, videoInfo, selectedFormat,
  status, progress, speed, downloaded, total, eta, fileUrl,
  canParse, canDownload, isDone, isDownloading,
  parse, download, reset,
} = useDownload()

function handleKeydown(e) {
  if (e.key === 'Enter' && canParse.value && !loading.value) {
    parse()
  }
}
</script>

<template>
  <div class="min-h-screen bg-[#f5f5f7] flex flex-col">
    <!-- Navbar -->
    <nav class="sticky top-0 z-50 bg-white/80 backdrop-blur-xl border-b border-gray-200">
      <div class="max-w-5xl mx-auto px-6 h-12 flex items-center justify-between">
        <div class="flex items-center gap-2">
          <svg class="w-5 h-5 text-[#0071e3]" fill="currentColor" viewBox="0 0 20 20">
            <path d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z"/>
          </svg>
          <span class="font-semibold text-[#1d1d1f] text-sm">万能下载</span>
        </div>
        <div class="flex items-center gap-4 text-xs text-[#6e6e73]">
          <a href="#" class="hover:text-[#1d1d1f]">功能</a>
          <a href="#" class="hover:text-[#1d1d1f]">定价</a>
        </div>
      </div>
    </nav>

    <!-- Hero -->
    <main class="flex-1 flex flex-col">
      <section class="pt-20 pb-12 px-6 text-center">
        <h1 class="text-4xl md:text-[56px] font-semibold text-[#1d1d1f] tracking-tight leading-tight mb-4">
          下载任何视频<br />只需一个链接
        </h1>
        <p class="text-[#6e6e73] text-lg md:text-xl mb-10">
          支持 YouTube、Bilibili、抖音、Twitter 等 1000+ 平台
        </p>

        <!-- Input -->
        <div class="max-w-2xl mx-auto">
          <div class="flex gap-3">
            <input
              v-model="url"
              @keydown="handleKeydown"
              type="url"
              placeholder="粘贴视频链接到这里..."
              class="flex-1 px-5 py-3.5 rounded-xl border border-gray-300 bg-white text-[#1d1d1f] text-base
                     focus:outline-none focus:ring-2 focus:ring-[#0071e3] focus:border-transparent
                     placeholder:text-gray-400 transition-all"
            />
            <button
              @click="parse"
              :disabled="!canParse || loading"
              class="px-8 py-3.5 bg-[#0071e3] text-white font-medium rounded-xl
                     hover:bg-[#0077ED] active:bg-[#006edb]
                     disabled:opacity-40 disabled:cursor-not-allowed
                     transition-all text-base whitespace-nowrap"
            >
              {{ loading ? '解析中...' : '解析' }}
            </button>
          </div>

          <!-- Error -->
          <p v-if="error" class="mt-3 text-red-500 text-sm">{{ error }}</p>
        </div>
      </section>

      <!-- Video Info -->
      <section v-if="videoInfo" class="max-w-2xl mx-auto w-full px-6 pb-16">
        <div class="bg-white rounded-2xl p-6 shadow-sm border border-gray-200">
          <div class="flex gap-4 mb-6">
            <img
              v-if="videoInfo.thumbnail"
              :src="videoInfo.thumbnail"
              alt=""
              class="w-40 h-24 object-cover rounded-lg flex-shrink-0 bg-gray-100"
              @error="($event.target).style.display = 'none'"
            />
            <div class="min-w-0">
              <h3 class="text-[#1d1d1f] font-semibold text-lg leading-snug mb-1 truncate">
                {{ videoInfo.title }}
              </h3>
              <p class="text-[#6e6e73] text-sm">
                {{ videoInfo.author }}
                <span v-if="videoInfo.duration"> · {{ formatDuration(videoInfo.duration) }}</span>
                <span v-if="videoInfo.platform"> · {{ videoInfo.platform }}</span>
              </p>
            </div>
          </div>

          <!-- Quality Selector -->
          <div class="mb-6">
            <label class="text-sm font-medium text-[#1d1d1f] mb-2 block">选择清晰度</label>
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <button
                v-for="fmt in videoInfo.formats"
                :key="fmt.format_id"
                @click="selectedFormat = fmt.format_id"
                :class="[
                  'px-3 py-2.5 rounded-xl border text-sm font-medium transition-all',
                  selectedFormat === fmt.format_id
                    ? 'border-[#0071e3] bg-blue-50 text-[#0071e3]'
                    : 'border-gray-200 text-[#1d1d1f] hover:border-gray-300'
                ]"
              >
                {{ fmt.resolution }}
                <span v-if="fmt.filesize" class="text-[#6e6e73] font-normal ml-1">
                  {{ formatFileSize(fmt.filesize) }}
                </span>
              </button>
            </div>
          </div>

          <!-- Download Button -->
          <button
            v-if="!isDone && !isDownloading"
            @click="download"
            :disabled="!canDownload"
            class="w-full py-3.5 bg-[#0071e3] text-white font-medium rounded-xl
                   hover:bg-[#0077ED] active:bg-[#006edb]
                   disabled:opacity-40 disabled:cursor-not-allowed transition-all text-base"
          >
            开始下载
          </button>

          <!-- Progress -->
          <div v-if="isDownloading" class="space-y-3">
            <div class="h-2 bg-gray-200 rounded-full overflow-hidden">
              <div
                class="h-full bg-[#0071e3] rounded-full transition-all duration-500"
                :style="{ width: `${progress}%` }"
              />
            </div>
            <div class="flex justify-between text-sm text-[#6e6e73]">
              <span>{{ progress }}%</span>
              <span v-if="speed">{{ speed }}</span>
              <span v-if="total">{{ formatFileSize(downloaded) }} / {{ formatFileSize(total) }}</span>
              <span v-if="eta">剩余 {{ eta }}s</span>
            </div>
            <p class="text-center text-sm text-[#6e6e73]">
              {{ status === 'merging' ? '正在合并音视频...' : '下载中...' }}
            </p>
          </div>

          <!-- Done -->
          <div v-if="isDone" class="text-center space-y-3">
            <p class="text-green-600 font-medium">下载完成</p>
            <a
              :href="fileUrl"
              download
              class="inline-block px-8 py-3.5 bg-[#0071e3] text-white font-medium rounded-xl
                     hover:bg-[#0077ED] transition-all text-base"
            >
              保存到本地
            </a>
            <div>
              <button
                @click="reset"
                class="text-sm text-[#0071e3] hover:underline mt-2"
              >
                继续下载其他视频
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- Features (shown when no video) -->
      <section v-if="!videoInfo" class="max-w-4xl mx-auto w-full px-6 pb-20">
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-5">
          <div class="bg-white rounded-2xl p-6 text-center border border-gray-200">
            <div class="text-3xl mb-3">🌐</div>
            <h3 class="text-[#1d1d1f] font-semibold mb-1">1000+ 平台</h3>
            <p class="text-[#6e6e73] text-sm">YouTube、Bilibili、抖音、Twitter 等全球主流平台</p>
          </div>
          <div class="bg-white rounded-2xl p-6 text-center border border-gray-200">
            <div class="text-3xl mb-3">🎬</div>
            <h3 class="text-[#1d1d1f] font-semibold mb-1">高清下载</h3>
            <p class="text-[#6e6e73] text-sm">支持 360p 到 4K 多种清晰度自由选择</p>
          </div>
          <div class="bg-white rounded-2xl p-6 text-center border border-gray-200">
            <div class="text-3xl mb-3">📱</div>
            <h3 class="text-[#1d1d1f] font-semibold mb-1">手机也能用</h3>
            <p class="text-[#6e6e73] text-sm">手机浏览器直接访问，随时随地下载视频</p>
          </div>
        </div>
      </section>
    </main>

    <!-- Footer -->
    <footer class="border-t border-gray-200 py-6 text-center text-xs text-[#6e6e73]">
      <p>仅供个人学习使用，请勿用于商业用途</p>
    </footer>
  </div>
</template>
