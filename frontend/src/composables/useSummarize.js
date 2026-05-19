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

  async function start(url, subtitleLang) {
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
      const res = await startSummarize(url, subtitleLang)
      summarizeTaskId.value = res.task_id
      _startPolling()
    } catch (e) {
      summarizeError.value = _extractError(e)
      summarizeLoading.value = false
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
    start, chat, reset,
  }
}
