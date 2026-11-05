import { ref, computed } from 'vue'
import { startSummarize, getSummarizeStatus, sendChatMessage } from '../api'

export function useSummarize() {
  const summarizeLoading = ref(false)
  const summarizeError = ref('')
  const summaryResult = ref(null)
  const summarizeTaskId = ref('')
  const summarizeStatus = ref('')   // preparing | transcribing | summarizing | done | error
  const summarizeMessage = ref('')
  const transcriptText = ref('')
  const subtitleData = ref([])
  const videoTitle = ref('')
  const mindmapMarkdown = ref('')

  const chatMessages = ref([])
  const chatLoading = ref(false)
  // 对话区域里的错误提示（请求失败 / 没有可用的字幕上下文）
  const chatError = ref('')

  let pollTimer = null

  // 没有字幕上下文时的提示：字幕是提问的依据，没有它就别去问 AI
  const CHAT_NO_CONTEXT_HINT = '还没有可用的字幕，暂时无法进行 AI 问答。'
  const CHAT_NO_CONTEXT_HINT_PARSED = 'AI 分析尚未完成，还没有可用的字幕可供提问。'

  // 提问的前提是字幕。没有字幕上下文时给出原因（AI 还没跑 / 视频没字幕），
  // 由面板展示，提示文案只有这一处。
  const chatHint = computed(() => {
    if (transcriptText.value.trim()) return ''
    return summarizeStatus.value === 'parsed'
      ? CHAT_NO_CONTEXT_HINT_PARSED
      : CHAT_NO_CONTEXT_HINT
  })

  function _extractError(err) {
    if (!err) return '未知错误'
    if (typeof err === 'string') return err
    if (err instanceof Error) return err.message || String(err)
    if (typeof err === 'object') {
      return err.detail || err.message || err.error || JSON.stringify(err)
    }
    return String(err)
  }

  async function start(url, subtitleLang, historyId) {
    summarizeError.value = ''
    summaryResult.value = null
    summarizeStatus.value = ''
    summarizeMessage.value = ''
    transcriptText.value = ''
    subtitleData.value = []
    mindmapMarkdown.value = ''
    chatMessages.value = []
    summarizeLoading.value = true

    try {
      const res = await startSummarize(url, subtitleLang, historyId)
      summarizeTaskId.value = res.task_id
      _startPolling()
    } catch (e) {
      summarizeError.value = _extractError(e)
      summarizeLoading.value = false
    }
  }

  /**
   * 把历史记录里的 AI 分析灌进现有状态（不触发新的 AI 任务）。
   *
   * 历史详情页用它展示当初跑出来的总结 / 字幕 / 思维导图；
   * AI 问答也复用这里灌好的字幕上下文。
   */
  function load(record) {
    if (!record) return
    _stopPolling()
    summaryResult.value = record.ai_result || null
    transcriptText.value = record.transcript || ''
    subtitleData.value = record.subtitle_data || []
    mindmapMarkdown.value = record.mindmap_markdown || ''
    videoTitle.value = record.title || ''
    summarizeTaskId.value = ''
    summarizeLoading.value = false
    chatMessages.value = []
    chatLoading.value = false
    chatError.value = ''

    if (record.status === 'ai_failed') {
      summarizeStatus.value = 'error'
      summarizeMessage.value = record.error || 'AI 总结失败'
      summarizeError.value = record.error || 'AI 总结失败'
    } else if (record.status === 'ai_done') {
      summarizeStatus.value = 'done'
      summarizeMessage.value = ''
      summarizeError.value = ''
    } else {
      // 只解析过、还没跑 AI
      summarizeStatus.value = 'parsed'
      summarizeMessage.value = 'AI 分析尚未完成'
      summarizeError.value = ''
    }
  }

  function _startPolling() {
    _stopPolling()
    pollTimer = setInterval(async () => {
      try {
        const s = await getSummarizeStatus(summarizeTaskId.value)
        summarizeStatus.value = s.status
        summarizeMessage.value = s.message || ''

        if (s.status === 'done') {
          summaryResult.value = s.result
          transcriptText.value = s.transcript || ''
          subtitleData.value = s.subtitle_data || []
          videoTitle.value = s.title || ''
          mindmapMarkdown.value = s.mindmap_markdown || ''
          summarizeLoading.value = false
          _stopPolling()
        } else if (s.status === 'error') {
          summarizeError.value = _extractError(s.error || 'AI 总结失败')
          summarizeLoading.value = false
          _stopPolling()
        }
      } catch {
        _stopPolling()
        summarizeLoading.value = false
        summarizeError.value = '网络连接失败，请检查后端服务'
      }
    }, 1500)
  }

  function _stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  async function chat(question) {
    if (!question.trim() || chatLoading.value) return
    chatError.value = ''
    // 没有字幕上下文就不发请求：记录可能没字幕，也可能还没跑过 AI。
    // 直接给提示，别拿空上下文去问一句。
    if (!transcriptText.value.trim()) {
      chatError.value = chatHint.value
      return
    }
    chatLoading.value = true
    chatMessages.value.push({ role: 'user', content: question })

    try {
      const res = await sendChatMessage(
        chatMessages.value.slice(-10),
        transcriptText.value
      )
      chatMessages.value.push(res.message)
    } catch (e) {
      // 错误显示在对话区域，不塞一条假回答冒充 AI 的回复
      chatError.value = `AI 对话失败: ${_extractError(e)}`
    } finally {
      chatLoading.value = false
    }
  }

  function reset() {
    _stopPolling()
    summarizeLoading.value = false
    summarizeError.value = ''
    summaryResult.value = null
    summarizeTaskId.value = ''
    summarizeStatus.value = ''
    summarizeMessage.value = ''
    transcriptText.value = ''
    subtitleData.value = []
    videoTitle.value = ''
    mindmapMarkdown.value = ''
    chatMessages.value = []
    chatLoading.value = false
    chatError.value = ''
  }

  return {
    summarizeLoading, summarizeError, summaryResult,
    summarizeTaskId, summarizeStatus, summarizeMessage,
    transcriptText, subtitleData, videoTitle, mindmapMarkdown,
    chatMessages, chatLoading, chatError, chatHint,
    start, load, chat, reset,
  }
}
