import { ref, computed } from 'vue'
import { parseVideo, startDownload, getDownloadStatus, getDownloadUrl } from '../api'

export function useDownload() {
  const url = ref('')
  const loading = ref(false)
  const error = ref('')
  const videoInfo = ref(null)
  const selectedFormat = ref('')
  const taskId = ref('')
  const status = ref('')
  const progress = ref(0)
  const speed = ref('')
  const downloaded = ref(0)
  const total = ref(0)
  const eta = ref(null)
  const fileUrl = ref('')
  let pollTimer = null

  const canParse = computed(() => url.value.trim().length > 0)
  const canDownload = computed(() => videoInfo.value && selectedFormat.value)
  const isDone = computed(() => status.value === 'done')
  const isDownloading = computed(() => status.value === 'downloading' || status.value === 'merging')

  async function parse() {
    error.value = ''
    videoInfo.value = null
    taskId.value = ''
    status.value = ''
    fileUrl.value = ''
    loading.value = true
    try {
      videoInfo.value = await parseVideo(url.value)
      if (videoInfo.value.formats.length > 0) {
        selectedFormat.value = videoInfo.value.formats[0].format_id
      }
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function download() {
    error.value = ''
    status.value = 'starting'
    try {
      const res = await startDownload(url.value, selectedFormat.value)
      taskId.value = res.task_id
      startPolling()
    } catch (e) {
      error.value = e.message
      status.value = 'error'
    }
  }

  function startPolling() {
    stopPolling()
    pollTimer = setInterval(async () => {
      try {
        const s = await getDownloadStatus(taskId.value)
        status.value = s.status
        progress.value = s.progress || 0
        speed.value = s.speed || ''
        downloaded.value = s.downloaded || 0
        total.value = s.total || 0
        eta.value = s.eta

        if (s.status === 'done') {
          fileUrl.value = getDownloadUrl(taskId.value)
          stopPolling()
        } else if (s.status === 'error') {
          error.value = s.error || '下载出错'
          stopPolling()
        }
      } catch {
        stopPolling()
      }
    }, 1000)
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  function reset() {
    stopPolling()
    url.value = ''
    videoInfo.value = null
    selectedFormat.value = ''
    taskId.value = ''
    status.value = ''
    progress.value = 0
    speed.value = ''
    downloaded.value = 0
    total.value = 0
    eta.value = null
    fileUrl.value = ''
    error.value = ''
  }

  return {
    url, loading, error, videoInfo, selectedFormat,
    taskId, status, progress, speed, downloaded, total, eta, fileUrl,
    canParse, canDownload, isDone, isDownloading,
    parse, download, reset,
  }
}
