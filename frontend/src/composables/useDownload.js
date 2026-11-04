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
  const elapsed = ref(0)
  let pollTimer = null
  let elapsedTimer = null

  const canParse = computed(() => url.value.trim().length > 0)
  const canDownload = computed(() => videoInfo.value && selectedFormat.value)
  const isDone = computed(() => status.value === 'done')
  const isDownloading = computed(() => status.value === 'downloading' || status.value === 'merging')
  const isStarting = computed(() => status.value === 'starting')

  async function parse() {
    error.value = ''
    videoInfo.value = null
    taskId.value = ''
    status.value = ''
    fileUrl.value = ''
    loading.value = true
    // 解析要经过多轮网络请求（代理节点偏慢时 YouTube 可能要 20s+），
    // 显示耗时让用户知道是在跑而不是卡死
    elapsed.value = 0
    stopElapsedTimer()
    elapsedTimer = setInterval(() => { elapsed.value++ }, 1000)
    try {
      videoInfo.value = await parseVideo(url.value)
      if (videoInfo.value.formats.length > 0) {
        selectedFormat.value = videoInfo.value.formats[0].format_id
      }
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
      stopElapsedTimer()
    }
  }

  function stopElapsedTimer() {
    if (elapsedTimer) {
      clearInterval(elapsedTimer)
      elapsedTimer = null
    }
  }

  async function download() {
    return downloadWith(url.value, selectedFormat.value)
  }

  /**
   * 按指定的 url + format_id 下载：流程与 download() 完全一致（同一个接口、
   * 同一套轮询与文件链接），区别是参数显式传入，不依赖组件内部状态。
   * 返回 task_id；失败时把原因写进 error 并返回 null。
   */
  async function downloadWith(targetUrl, formatId) {
    error.value = ''
    status.value = 'starting'
    try {
      const res = await startDownload(targetUrl, formatId)
      taskId.value = res.task_id
      startPolling()
      return res.task_id
    } catch (e) {
      error.value = e.message
      status.value = 'error'
      return null
    }
  }

  /**
   * 接管一个已经启动好的下载任务：历史记录下载的 task_id 由
   * POST /api/history/{id}/download 返回，这里只负责轮询进度与出文件链接。
   */
  function track(id) {
    taskId.value = id
    status.value = 'starting'
    startPolling()
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
    url, loading, error, videoInfo, selectedFormat, elapsed,
    taskId, status, progress, speed, downloaded, total, eta, fileUrl,
    canParse, canDownload, isDone, isDownloading, isStarting,
    parse, download, downloadWith, track, reset,
  }
}
