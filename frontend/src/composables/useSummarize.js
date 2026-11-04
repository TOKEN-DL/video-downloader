import { ref } from 'vue'
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

  let pollTimer = null

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
    chatLoading.value = true
    chatMessages.value.push({ role: 'user', content: question })

    try {
      const res = await sendChatMessage(
        chatMessages.value.slice(-10),
        transcriptText.value
      )
      chatMessages.value.push(res.message)
    } catch (e) {
      chatMessages.value.push({ role: 'assistant', content: `出错了: ${_extractError(e)}` })
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
  }

  return {
    summarizeLoading, summarizeError, summaryResult,
    summarizeTaskId, summarizeStatus, summarizeMessage,
    transcriptText, subtitleData, videoTitle, mindmapMarkdown,
    chatMessages, chatLoading,
    start, load, chat, reset,
  }
}
