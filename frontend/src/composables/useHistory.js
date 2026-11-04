import { ref, computed } from 'vue'
import { listHistory, getHistory, deleteHistory, clearHistory } from '../api'

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
    error.value = ''
    try {
      await deleteHistory(id)
      items.value = items.value.filter(item => item.id !== id)
      total.value = Math.max(0, total.value - 1)
      return true
    } catch (e) {
      error.value = e.message
      return false
    }
  }

  // 清空全部
  async function clearAll() {
    error.value = ''
    try {
      await clearHistory()
      items.value = []
      total.value = 0
      return true
    } catch (e) {
      error.value = e.message
      return false
    }
  }

  return {
    items, total, page, hasMore,
    loading, loadingMore, error,
    detail, detailLoading,
    load, loadMore, loadDetail, remove, clearAll,
  }
}
