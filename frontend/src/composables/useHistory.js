import { ref, computed } from 'vue'
import { listHistory } from '../api'

const PAGE_SIZE = 20

export function useHistory() {
  const items = ref([])
  const total = ref(0)
  const page = ref(0)
  const loading = ref(false)
  const loadingMore = ref(false)
  const error = ref('')

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

  return {
    items, total, page, hasMore,
    loading, loadingMore, error,
    load, loadMore,
  }
}
