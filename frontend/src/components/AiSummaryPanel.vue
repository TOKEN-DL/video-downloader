<template>
  <div class="bg-white rounded-2xl border border-gray-100 shadow-lg overflow-hidden h-full flex flex-col">
    <!-- Tab 导航 -->
    <div class="flex border-b border-gray-100">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        @click="activeTab = tab.key"
        class="relative flex items-center gap-1.5 px-5 py-3.5 text-sm font-medium transition-colors cursor-pointer"
        :class="activeTab === tab.key ? 'text-[#0071e3]' : 'text-[#86868b] hover:text-[#1d1d1f]'"
      >
        <span>{{ tab.icon }}</span>
        <span>{{ tab.label }}</span>
        <div v-if="activeTab === tab.key" class="absolute bottom-0 left-0 right-0 h-0.5 bg-[#0071e3]"></div>
      </button>
    </div>

    <!-- 内容区域 -->
    <div class="p-5 sm:p-6 flex-1 min-h-[400px]">

      <!-- ===== 总结 Tab ===== -->
      <div v-show="activeTab === 'summary'" class="h-full flex flex-col">
        <div v-if="loading && !summaryHtml" class="flex flex-col items-center justify-center py-16">
          <div class="w-10 h-10 border-4 border-[#0071e3]/20 border-t-[#0071e3] rounded-full animate-spin mb-4"></div>
          <p class="text-[#86868b] text-sm">{{ statusMessage }}</p>
        </div>
        <div v-if="summaryHtml" class="flex-1 overflow-y-auto max-h-[600px] pr-1">
          <div class="summary-prose prose prose-slate prose-sm max-w-none" v-html="summaryHtml"></div>
        </div>
        <div v-if="loading && summaryHtml" class="mt-2 inline-flex items-center gap-1.5 text-xs text-[#86868b]">
          <span class="w-1.5 h-1.5 bg-[#0071e3] rounded-full animate-pulse"></span>
          AI 正在生成中...
        </div>
      </div>

      <!-- ===== 字幕 Tab ===== -->
      <div v-show="activeTab === 'subtitle'">
        <div v-if="subtitleData && subtitleData.length" class="max-h-[500px] overflow-y-auto">
          <div class="flex items-center justify-between mb-3">
            <span class="text-sm text-[#86868b]">字幕文本</span>
            <div class="flex items-center gap-3">
              <div class="relative">
                <button @click="showFormatMenu = !showFormatMenu" class="text-xs text-[#0071e3] hover:underline cursor-pointer flex items-center gap-0.5">
                  下载
                  <svg class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7"/></svg>
                </button>
                <div v-if="showFormatMenu" class="absolute right-0 top-6 bg-white border border-gray-200 rounded-lg shadow-lg py-1 z-10 min-w-[80px]">
                  <button @click="downloadSubtitle('srt')" class="w-full text-left px-3 py-1.5 text-xs text-[#1d1d1f] hover:bg-gray-50">SRT 字幕</button>
                  <button @click="downloadSubtitle('txt')" class="w-full text-left px-3 py-1.5 text-xs text-[#1d1d1f] hover:bg-gray-50">TXT 文本</button>
                </div>
              </div>
              <button @click="copyTranscript" class="text-xs text-[#0071e3] hover:underline cursor-pointer">
                {{ transcriptCopied ? '已复制' : '复制' }}
              </button>
            </div>
          </div>
          <div v-for="(item, i) in subtitleData" :key="i" class="flex gap-3 py-2 px-3 rounded-lg hover:bg-gray-50 transition-colors">
            <span class="text-xs text-[#0071e3] font-mono shrink-0 pt-0.5 w-10 text-right">{{ item.time }}</span>
            <span class="text-sm text-[#1d1d1f] leading-relaxed">{{ item.text }}</span>
          </div>
        </div>
        <div v-else-if="transcript" class="space-y-1 max-h-[500px] overflow-y-auto">
          <div class="flex items-center justify-between mb-3">
            <span class="text-sm text-[#86868b]">字幕文本</span>
            <button @click="copyTranscript" class="text-xs text-[#0071e3] hover:underline cursor-pointer">
              {{ transcriptCopied ? '已复制' : '复制全部' }}
            </button>
          </div>
          <div v-for="(line, i) in transcriptLines" :key="i" class="flex gap-3 py-2 px-3 rounded-lg hover:bg-gray-50 transition-colors">
            <span class="text-sm text-[#1d1d1f] leading-relaxed">{{ line }}</span>
          </div>
        </div>
        <div v-else-if="loading" class="flex flex-col items-center justify-center py-16">
          <div class="w-10 h-10 border-4 border-[#0071e3]/20 border-t-[#0071e3] rounded-full animate-spin mb-3"></div>
          <p class="text-[#86868b] text-sm">正在提取字幕...</p>
        </div>
        <div v-else class="flex flex-col items-center justify-center py-16 text-[#86868b]">
          <svg class="w-10 h-10 mb-3 opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
          </svg>
          <p class="text-sm">该视频暂无可用字幕</p>
        </div>
      </div>

      <!-- ===== 思维导图 Tab ===== -->
      <div v-if="activeTab === 'mindmap'">
        <div v-if="mindmapMarkdown">
          <MindMapView :markdown="mindmapMarkdown" />
        </div>
        <div v-else-if="loading" class="flex flex-col items-center justify-center py-16">
          <div class="w-10 h-10 border-4 border-[#0071e3]/20 border-t-[#0071e3] rounded-full animate-spin mb-3"></div>
          <p class="text-[#86868b] text-sm">正在生成思维导图...</p>
        </div>
        <div v-else class="flex flex-col items-center justify-center py-16 text-[#86868b]">
          <p class="text-sm">请先生成总结以查看思维导图</p>
        </div>
      </div>

      <!-- ===== AI 对话 Tab ===== -->
      <div v-show="activeTab === 'chat'">
        <div class="flex flex-col" style="height: 420px">
          <!-- 消息列表 -->
          <div ref="chatContainer" class="flex-1 overflow-y-auto space-y-4 pr-1">
            <div v-if="chatMessages.length === 0" class="flex flex-col items-center justify-center py-12 text-[#86868b]">
              <p class="text-sm mb-1">向 AI 提问关于这个视频的任何问题</p>
              <p class="text-xs">例如："这个视频的核心观点是什么？"</p>
            </div>
            <div
              v-for="(msg, idx) in chatMessages"
              :key="idx"
              class="flex"
              :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
            >
              <div
                class="max-w-[80%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed"
                :class="msg.role === 'user'
                  ? 'bg-[#0071e3] text-white rounded-br-md'
                  : 'bg-gray-50 text-[#1d1d1f] rounded-bl-md border border-gray-100'"
              >
                <div v-if="msg.role === 'assistant'" class="chat-prose prose prose-slate prose-sm max-w-none" v-html="renderMd(msg.content)"></div>
                <span v-else>{{ msg.content }}</span>
                <span v-if="msg.role === 'assistant' && chatLoading && idx === chatMessages.length - 1"
                  class="inline-block w-1.5 h-4 bg-[#0071e3]/60 rounded-sm animate-pulse ml-0.5 align-text-bottom"></span>
              </div>
            </div>
          </div>
          <!-- 输入区域 -->
          <div class="flex gap-2 pt-3 border-t border-gray-100 mt-2">
            <input
              v-model="chatInput"
              @keydown.enter.prevent="sendChat"
              type="text"
              placeholder="输入你的问题..."
              class="flex-1 h-11 px-4 rounded-xl border border-gray-200 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-[#0071e3]/20 focus:border-[#0071e3] transition-all"
              :disabled="chatLoading"
            />
            <button
              @click="sendChat"
              :disabled="!chatInput.trim() || chatLoading"
              class="h-11 px-5 rounded-xl bg-[#0071e3] text-white text-sm font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer hover:bg-[#0077ed]"
            >
              发送
            </button>
          </div>
        </div>
      </div>

      <!-- ===== 错误提示 ===== -->
      <div v-if="error && !loading" class="flex flex-col items-center justify-center py-16">
        <div class="text-red-500 text-sm mb-3">{{ error }}</div>
        <button @click="$emit('retry')" class="text-sm text-[#0071e3] hover:underline cursor-pointer">重试</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { marked } from 'marked'
import MindMapView from './MindMapView.vue'

marked.setOptions({ breaks: true, gfm: true })

const props = defineProps({
  loading: Boolean,
  error: String,
  result: Object,
  status: String,
  message: String,
  transcript: String,
  subtitleData: Array,
  mindmapMarkdown: String,
  chatMessages: Array,
  chatLoading: Boolean,
})
const emit = defineEmits(['chat', 'retry'])

const activeTab = ref('summary')
const chatInput = ref('')
const chatContainer = ref(null)
const transcriptCopied = ref(false)
const subtitleFormat = ref('srt')
const showFormatMenu = ref(false)

const tabs = [
  { key: 'summary', label: '总结', icon: '📝' },
  { key: 'subtitle', label: '字幕', icon: '📄' },
  { key: 'mindmap', label: '思维导图', icon: '🧠' },
  { key: 'chat', label: 'AI 问答', icon: '💬' },
]

// 将结构化结果转为 Markdown 并渲染
const summaryHtml = computed(() => {
  const r = props.result
  if (!r) return ''
  const parts = []
  if (r.summary) {
    parts.push(`## 概述\n\n${r.summary}`)
  }
  if (r.highlights?.length) {
    parts.push('## 核心要点\n\n' + r.highlights.map(h => `- **[${h.timestamp}]** ${h.point}`).join('\n'))
  }
  if (r.terms?.length) {
    parts.push('## 关键术语\n\n' + r.terms.map(t => `- **${t.term}** — ${t.explanation}`).join('\n'))
  }
  if (r.qa?.length) {
    parts.push('## 深度思考\n\n' + r.qa.map(q => `**Q: ${q.question}**\n\n${q.answer}`).join('\n\n'))
  }
  const md = parts.join('\n\n---\n\n')
  return marked.parse(md)
})

const statusMessage = computed(() => {
  const map = {
    preparing: '准备中...',
    transcribing: '正在提取字幕...',
    summarizing: 'AI 正在分析视频内容...',
  }
  return map[props.status] || props.message || '处理中...'
})

const transcriptLines = computed(() => {
  if (!props.transcript) return []
  return props.transcript.split('\n').filter(l => l.trim())
})

function renderMd(text) {
  if (!text) return ''
  return marked.parse(text)
}

function sendChat() {
  const q = chatInput.value.trim()
  if (!q || props.chatLoading) return
  chatInput.value = ''
  emit('chat', q)
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

function copyTranscript() {
  if (!props.transcript) return
  navigator.clipboard.writeText(props.transcript).then(() => {
    transcriptCopied.value = true
    setTimeout(() => { transcriptCopied.value = false }, 2000)
  })
}

function _parseTime(timeStr) {
  const parts = timeStr.split(':')
  const min = parseInt(parts[0]) || 0
  const sec = parseInt(parts[1]) || 0
  const totalSec = min * 60 + sec
  const h = String(Math.floor(totalSec / 3600)).padStart(2, '0')
  const m = String(Math.floor((totalSec % 3600) / 60)).padStart(2, '0')
  const s = String(totalSec % 60).padStart(2, '0')
  return `${h}:${m}:${s},000`
}

function generateSrt() {
  const data = props.subtitleData
  if (!data || !data.length) return ''
  return data.map((item, i) => {
    const next = data[i + 1]
    const end = next ? _parseTime(next.time) : _parseTime(item.time).replace(',000', ',500')
    return `${i + 1}\n${_parseTime(item.time)} --> ${end}\n${item.text}`
  }).join('\n\n')
}

function generateTxt() {
  const data = props.subtitleData
  if (!data || !data.length) return props.transcript || ''
  return data.map(item => `${item.time}  ${item.text}`).join('\n')
}

function downloadSubtitle(format) {
  showFormatMenu.value = false
  const content = format === 'srt' ? generateSrt() : generateTxt()
  if (!content) return
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `subtitle.${format}`
  a.click()
  URL.revokeObjectURL(url)
}

watch(() => props.chatMessages.length, async () => {
  await nextTick()
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
})

// Close format menu on outside click
function handleClickOutside(e) {
  if (showFormatMenu.value && !e.target.closest('.relative')) {
    showFormatMenu.value = false
  }
}
onMounted(() => document.addEventListener('click', handleClickOutside))
onUnmounted(() => document.removeEventListener('click', handleClickOutside))
</script>

<style scoped>
/* 总结 Markdown 排版 */
.summary-prose :deep(h2) {
  font-size: 1.1rem;
  font-weight: 700;
  margin-top: 1.5rem;
  margin-bottom: 0.75rem;
  color: #1d1d1f;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid #f0f0f0;
}
.summary-prose :deep(h2:first-child) {
  margin-top: 0;
}
.summary-prose :deep(p) {
  margin-bottom: 0.75rem;
  line-height: 1.8;
  color: #1d1d1f;
}
.summary-prose :deep(ul) {
  margin-bottom: 0.75rem;
  padding-left: 1.25rem;
}
.summary-prose :deep(li) {
  margin-bottom: 0.4rem;
  line-height: 1.8;
}
.summary-prose :deep(li::marker) {
  color: #0071e3;
}
.summary-prose :deep(strong) {
  color: #1d1d1f;
  font-weight: 600;
}
.summary-prose :deep(hr) {
  margin: 1.25rem 0;
  border-color: #f0f0f0;
}

/* 对话 Markdown */
.chat-prose :deep(p) {
  margin-bottom: 0.4rem;
  line-height: 1.7;
}
.chat-prose :deep(p:last-child) {
  margin-bottom: 0;
}
.chat-prose :deep(ul), .chat-prose :deep(ol) {
  margin-bottom: 0.4rem;
  padding-left: 1rem;
}
.chat-prose :deep(li) {
  margin-bottom: 0.2rem;
  line-height: 1.7;
}
.chat-prose :deep(strong) {
  font-weight: 600;
}
</style>
