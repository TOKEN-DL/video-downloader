<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useHistory } from '../composables/useHistory'
import HistoryThumb from '../components/HistoryThumb.vue'
import { formatFileSize, formatDuration } from '../api'

const route = useRoute()

const { detail, detailLoading, error, loadDetail } = useHistory()

// 清晰度选择：默认选中第一档
const selectedFormat = ref('')
const formats = computed(() => detail.value?.formats || [])

watch(formats, (list) => {
  if (list.length && !list.some(f => f.format_id === selectedFormat.value)) {
    selectedFormat.value = list[0].format_id
  }
})

onMounted(() => loadDetail(route.params.id))
</script>

<template>
  <div class="min-h-screen bg-white flex flex-col font-sans">

    <!-- ═══ Navbar ═══ -->
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
          <router-link to="/history" class="text-[#1d1d1f] font-medium">历史记录</router-link>
          <router-link to="/" class="hover:text-[#1d1d1f] transition-colors">返回首页</router-link>
        </div>
      </div>
    </nav>

    <!-- ═══ Content ═══ -->
    <section class="flex-1 px-6 py-10 md:py-14">
      <div class="max-w-[1200px] mx-auto">

        <!-- Back -->
        <router-link
          to="/history"
          class="inline-flex items-center gap-1.5 text-xs text-[#86868b] hover:text-[#1d1d1f] transition-colors mb-6"
        >
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7"/>
          </svg>
          返回历史记录
        </router-link>

        <!-- Loading -->
        <div v-if="detailLoading" class="py-20 text-center text-sm text-[#86868b]">
          正在加载记录...
        </div>

        <!-- Error -->
        <div v-else-if="error" class="py-20 text-center animate-fade-in-up">
          <div class="w-14 h-14 mx-auto mb-5 bg-red-50 rounded-2xl flex items-center justify-center">
            <svg class="w-7 h-7 text-red-500" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
            </svg>
          </div>
          <h2 class="text-[#1d1d1f] text-lg font-semibold mb-2">{{ error }}</h2>
          <router-link
            to="/history"
            class="inline-flex items-center gap-2 px-6 py-3 bg-[#0071e3] text-white font-semibold rounded-xl
                   hover:bg-[#0077ed] active:scale-[0.98] transition-all text-sm shadow-sm"
          >
            返回历史记录
          </router-link>
        </div>

        <!-- Record -->
        <div v-else-if="detail" class="grid grid-cols-1 lg:grid-cols-5 gap-5">

          <!-- ── Left: Video Info Card ── -->
          <div class="lg:col-span-2 bg-white rounded-2xl border border-gray-100 shadow-lg overflow-hidden self-start">
            <!-- Cover -->
            <div class="relative w-full aspect-video bg-gray-100 overflow-hidden">
              <!-- 封面优先读本地缓存，取不到自动回退远程代理图 -->
              <HistoryThumb v-if="detail.thumbnail || detail.thumb_path" :record="detail" alt="" class="w-full h-full object-cover" />
              <div class="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent"></div>
              <div v-if="detail.duration"
                   class="absolute bottom-2 right-2 bg-black/70 text-white text-[10px] px-1.5 py-0.5 rounded-md backdrop-blur-sm">
                {{ formatDuration(detail.duration) }}
              </div>
              <div v-if="detail.platform"
                   class="absolute top-2 left-2 bg-black/50 text-white text-[9px] px-2 py-0.5 rounded-full font-medium uppercase tracking-wider backdrop-blur-sm">
                {{ detail.platform }}
              </div>
              <div class="absolute bottom-0 left-0 right-0 p-3 md:p-4">
                <h3 class="text-white font-semibold text-sm md:text-base leading-snug line-clamp-2 drop-shadow-md">
                  {{ detail.title }}
                </h3>
                <p v-if="detail.author" class="text-white/70 text-[11px] md:text-xs mt-0.5 drop-shadow-sm">
                  {{ detail.author }}
                </p>
              </div>
            </div>

            <!-- Quality Selector -->
            <div class="p-4">
              <label class="text-[10px] font-medium text-[#86868b] uppercase tracking-wider mb-2 block">选择清晰度</label>
              <div v-if="formats.length" class="grid grid-cols-2 gap-1.5">
                <button
                  v-for="fmt in formats"
                  :key="fmt.format_id"
                  @click="selectedFormat = fmt.format_id"
                  :class="[
                    'px-2.5 py-2.5 rounded-xl text-xs font-medium transition-all text-center',
                    selectedFormat === fmt.format_id
                      ? 'bg-[#0071e3] text-white shadow-sm shadow-blue-200'
                      : 'bg-[#f5f5f7] text-[#1d1d1f] hover:bg-[#e8e8ed] active:scale-[0.97]'
                  ]"
                >
                  <div>{{ fmt.resolution }}</div>
                  <div v-if="fmt.filesize" class="text-[9px] mt-0.5 opacity-60">
                    {{ formatFileSize(fmt.filesize) }}
                  </div>
                </button>
              </div>
              <p v-else class="text-xs text-[#86868b] py-2">这条记录没有可用的清晰度信息。</p>
            </div>
          </div>

          <!-- ── Right: AI Panel Placeholder ── -->
          <div class="lg:col-span-3">
            <div class="h-full min-h-[280px] rounded-2xl border border-dashed border-gray-200 bg-[#f5f5f7]
                        p-8 flex flex-col items-center justify-center text-center">
              <div class="w-12 h-12 mb-4 bg-white rounded-2xl flex items-center justify-center shadow-sm">
                <svg class="w-6 h-6 text-[#0071e3]" fill="none" stroke="currentColor" stroke-width="1.6" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round"
                        d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456z"/>
                </svg>
              </div>
              <h3 class="text-[#1d1d1f] font-semibold text-sm mb-1.5">AI 分析内容</h3>
              <p class="text-[#86868b] text-xs leading-relaxed max-w-xs">
                该视频的 AI 总结、字幕与思维导图会显示在这里。
              </p>
            </div>
          </div>
        </div>

      </div>
    </section>
  </div>
</template>
