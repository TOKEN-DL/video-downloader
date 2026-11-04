<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useHistory } from '../composables/useHistory'
import { useSummarize } from '../composables/useSummarize'
import HistoryThumb from '../components/HistoryThumb.vue'
import AiSummaryPanel from '../components/AiSummaryPanel.vue'
import { formatFileSize, formatDuration, getHistoryExportUrl } from '../api'

const route = useRoute()
const router = useRouter()

const { detail, detailLoading, error, loadDetail } = useHistory()

// AI 面板的数据来自库里那条记录，不是当场再跑一次 AI
const {
  summarizeLoading, summarizeError, summaryResult,
  summarizeStatus, summarizeMessage,
  transcriptText, subtitleData, mindmapMarkdown,
  chatMessages, chatLoading,
  load: loadSummary, chat,
} = useSummarize()

// 清晰度选择：默认选中第一档
const selectedFormat = ref('')
const formats = computed(() => detail.value?.formats || [])

// 导出：历史记录没有内存里的 task_id，走按记录的导出接口
const exportMarkdownUrl = computed(() =>
  detail.value ? getHistoryExportUrl(detail.value.id, 'markdown') : ''
)
const exportPdfUrl = computed(() =>
  detail.value ? getHistoryExportUrl(detail.value.id, 'pdf') : ''
)

watch(formats, (list) => {
  if (list.length && !list.some(f => f.format_id === selectedFormat.value)) {
    selectedFormat.value = list[0].format_id
  }
})

// AI 失败后想重来：带着原链接回首页重新解析
function handleRetry() {
  if (!detail.value?.url) return
  router.push({ path: '/', query: { url: detail.value.url } })
}

onMounted(async () => {
  const record = await loadDetail(route.params.id)
  if (record) loadSummary(record)
})
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

          <!-- ── Right: AI Panel ── -->
          <div class="lg:col-span-3">

            <!-- AI 失败：记录保留，标出失败原因 -->
            <div v-if="detail.status === 'ai_failed'"
                 class="mb-3 rounded-2xl border border-orange-200 bg-orange-50 px-4 py-3 flex items-start gap-3">
              <svg class="w-4 h-4 mt-0.5 shrink-0 text-orange-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
              </svg>
              <div class="flex-1 min-w-0">
                <p class="text-xs font-semibold text-orange-700">AI 总结失败</p>
                <p class="text-xs text-orange-600 mt-0.5 break-words">{{ detail.error || '未知原因' }}</p>
                <p class="text-[11px] text-orange-500 mt-1">视频信息已保留，可回到首页重新解析该链接再试一次。</p>
              </div>
            </div>

            <!-- 只解析过、还没跑 AI -->
            <div v-else-if="detail.status === 'parsed'"
                 class="mb-3 rounded-2xl border border-gray-200 bg-[#f5f5f7] px-4 py-3">
              <p class="text-xs text-[#86868b]">AI 分析尚未完成。回到首页重新解析该链接，可再跑一次 AI 总结。</p>
            </div>

            <!-- AI 面板：总结 / 字幕 / 思维导图 / AI 问答 -->
            <AiSummaryPanel
              :loading="summarizeLoading"
              :error="summarizeError"
              :result="summaryResult"
              :status="summarizeStatus"
              :message="summarizeMessage"
              :transcript="transcriptText"
              :subtitle-data="subtitleData"
              :mindmap-markdown="mindmapMarkdown"
              :chat-messages="chatMessages"
              :chat-loading="chatLoading"
              @chat="chat"
              @retry="handleRetry"
            />

            <!-- 导出总结 -->
            <div class="mt-3 flex items-center gap-2">
              <a
                :href="exportMarkdownUrl"
                download
                class="inline-flex items-center gap-1.5 px-3.5 py-2 bg-white border border-gray-200 rounded-xl text-xs
                       font-medium text-[#1d1d1f] hover:bg-[#f5f5f7] active:scale-[0.98] transition-all"
              >
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                </svg>
                导出 Markdown
              </a>
              <a
                :href="exportPdfUrl"
                download
                class="inline-flex items-center gap-1.5 px-3.5 py-2 bg-white border border-gray-200 rounded-xl text-xs
                       font-medium text-[#1d1d1f] hover:bg-[#f5f5f7] active:scale-[0.98] transition-all"
              >
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                </svg>
                导出 PDF
              </a>
            </div>
          </div>
        </div>

      </div>
    </section>
  </div>
</template>
