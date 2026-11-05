import { ref, computed } from 'vue'
import { listHistory, getHistory, deleteHistory, clearHistory, downloadHistory } from '../api'

const PAGE_SIZE = 20

export function useHistory() {
  const items = ref([])
  const total = ref(0)
  const page = ref(0)
  const loading = ref(false)
  const loadingMore = ref(false)
  const error = ref('')

  const detail = ref(null)
  const detailLoading = ref(false)
  // 下载失败单独放：error 是列表 / 详情的加载错误，两者不能混
  const downloadError = ref('')
  // 删除 / 清空失败也单独放：详情页里加载错误会让整页变成错误页，
  // 删除失败不该把正在看的记录也一起顶掉
  const actionError = ref('')

  const hasMore = computed(() => items.value.length < total.value)

  // 首次加载：直接替换整个列表
  async function load() {
    error.value = ''
    loading.value = true
    try {
      const res = await listHistory(1, PAGE_SIZE)
      items.value = res.items || []
      total.value = res.total || 0
      page.value = 1
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  // 「加载更多」：按页追加，不翻页
  async function loadMore() {
    if (!hasMore.value || loadingMore.value) return
    error.value = ''
    loadingMore.value = true
    try {
      const next = page.value + 1
      const res = await listHistory(next, PAGE_SIZE)
      items.value = items.value.concat(res.items || [])
      total.value = res.total || 0
      page.value = next
    } catch (e) {
      error.value = e.message
    } finally {
      loadingMore.value = false
    }
  }

  // 记录详情（详情页用）
  async function loadDetail(id) {
    error.value = ''
    detail.value = null
    detailLoading.value = true
    try {
      detail.value = await getHistory(id)
      return detail.value
    } catch (e) {
      error.value = e.message
      return null
    } finally {
      detailLoading.value = false
    }
  }

  // 删除单条：后端删成功后本地列表同步去掉这一条
  async function remove(id) {
    actionError.value = ''
    try {
      await deleteHistory(id)
      items.value = items.value.filter(item => item.id !== id)
      total.value = Math.max(0, total.value - 1)
      return true
    } catch (e) {
      actionError.value = e.message
      return false
    }
  }

  // 从历史记录重新下载：服务端用记录里的链接与清晰度重新走网络下载。
  // 成功返回 task_id，失败把原因写进 downloadError 并返回 null。
  async function startDownload(id, formatId) {
    downloadError.value = ''
    try {
      const res = await downloadHistory(id, formatId)
      return res.task_id
    } catch (e) {
      downloadError.value = e.message
      return null
    }
  }

  // 清空全部
  async function clearAll() {
    actionError.value = ''
    try {
      await clearHistory()
      items.value = []
      total.value = 0
      return true
    } catch (e) {
      actionError.value = e.message
      return false
    }
  }

  return {
    items, total, page, hasMore,
    loading, loadingMore, error, actionError,
    detail, detailLoading, downloadError,
    load, loadMore, loadDetail, remove, clearAll, startDownload,
  }
}
