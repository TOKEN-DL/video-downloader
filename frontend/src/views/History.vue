<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useHistory } from '../composables/useHistory'
import { HISTORY_STATUS, HISTORY_STATUS_META } from '../constants/history'
import AppNavbar from '../components/AppNavbar.vue'
import HistoryCover from '../components/HistoryCover.vue'

const router = useRouter()

const {
  items, total, hasMore,
  loading, loadingMore, error, actionError,
  load, loadMore, remove, clearAll,
} = useHistory()

// 清空全部要二次确认：第一次点只亮出确认按钮
const confirmingClear = ref(false)
// 正在删除的记录 id，避免连点触发多次请求
const deletingId = ref(null)

// 状态徽标：parsed=已解析，ai_done=AI 已总结，ai_failed=AI 失败
function statusMeta(status) {
  return HISTORY_STATUS_META[status] || HISTORY_STATUS_META[HISTORY_STATUS.PARSED]
}

// 徽标的 hover 提示：AI 失败时给出失败原因，
// 让用户能区分「没字幕」和「模型报错」，而不是只看到一个「AI 失败」。
function statusTitle(item) {
  if (item.status === HISTORY_STATUS.AI_FAILED) {
    return item.error || '未知原因'
  }
  return statusMeta(item.status).label
}

// 后端存的是 "YYYY-MM-DD HH:MM:SS"，展示到分钟即可
function formatTime(value) {
  return value ? String(value).slice(0, 16) : ''
}

function openDetail(id) {
  router.push(`/history/${id}`)
}

async function handleDelete(id) {
  if (deletingId.value !== null) return
  deletingId.value = id
  try {
    await remove(id)
  } finally {
    deletingId.value = null
  }
}

function askClear() {
  confirmingClear.value = true
}

function cancelClear() {
  confirmingClear.value = false
}

async function confirmClear() {
  const ok = await clearAll()
  if (ok) confirmingClear.value = false
}

onMounted(load)
</script>

<template>
  <div class="min-h-screen bg-white flex flex-col font-sans">

    <!-- ═══ Navbar ═══ -->
    <AppNavbar>
      <router-link to="/history" class="text-[#1d1d1f] font-medium">历史记录</router-link>
      <router-link to="/" class="hover:text-[#1d1d1f] transition-colors">返回首页</router-link>
    </AppNavbar>

    <!-- ═══ Content ═══ -->
    <section class="flex-1 px-6 py-10 md:py-14">
      <div class="max-w-[1200px] mx-auto">

        <!-- Header -->
        <div class="flex items-center justify-between gap-4 mb-8">
          <div class="flex items-baseline gap-4">
            <h1 class="text-[#1d1d1f] text-2xl md:text-[32px] font-semibold tracking-tight">历史记录</h1>
            <span v-if="total > 0" class="text-xs text-[#86868b] tabular-nums">共 {{ total }} 条</span>
          </div>

          <!-- 清空全部：二次确认 -->
          <div v-if="total > 0" class="flex items-center gap-2">
            <template v-if="confirmingClear">
              <span class="text-xs text-[#86868b]">确认清空全部？</span>
              <button
                @click="confirmClear"
                class="px-3 py-1.5 bg-red-500 text-white font-medium rounded-lg text-xs
                       hover:bg-red-600 active:scale-[0.97] transition-all"
              >
                确认清空
              </button>
              <button
                @click="cancelClear"
                class="px-3 py-1.5 bg-[#f5f5f7] text-[#1d1d1f] font-medium rounded-lg text-xs
                       hover:bg-[#e8e8ed] active:scale-[0.97] transition-all"
              >
                取消
              </button>
            </template>
            <button
              v-else
              @click="askClear"
              class="px-3 py-1.5 bg-[#f5f5f7] text-[#86868b] font-medium rounded-lg text-xs
                     hover:bg-red-50 hover:text-red-500 active:scale-[0.97] transition-all"
            >
              清空全部
            </button>
          </div>
        </div>

        <!-- Error -->
        <p v-if="error || actionError" class="mb-6 text-red-500 text-sm flex items-center justify-center gap-1.5">
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
          </svg>
          {{ error || actionError }}
        </p>

        <!-- Loading -->
        <div v-if="loading" class="py-20 text-center text-sm text-[#86868b]">
          正在加载历史记录...
        </div>

        <!-- Empty State -->
        <div v-else-if="items.length === 0" class="py-20 text-center animate-fade-in-up">
          <div class="w-14 h-14 mx-auto mb-5 bg-blue-50 rounded-2xl flex items-center justify-center">
            <svg class="w-7 h-7 text-[#0071e3]" fill="none" stroke="currentColor" stroke-width="1.6" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round"
                    d="M12 8v4l3 2m6-2a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
          </div>
          <h2 class="text-[#1d1d1f] text-lg font-semibold mb-2">还没有历史记录</h2>
          <p class="text-[#86868b] text-sm mb-6">解析过的视频会自动保存在这里，随时回看封面、标题与时长。</p>
          <router-link
            to="/"
            class="inline-flex items-center gap-2 px-6 py-3 bg-[#0071e3] text-white font-semibold rounded-xl
                   hover:bg-[#0077ed] active:scale-[0.98] transition-all text-sm shadow-sm"
          >
            去解析第一个视频
          </router-link>
        </div>

        <!-- Cards -->
        <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-5">
          <article
            v-for="item in items"
            :key="item.id"
            @click="openDetail(item.id)"
            class="card-hover bg-white rounded-2xl border border-gray-100 shadow-lg overflow-hidden cursor-pointer"
          >
            <HistoryCover :record="item" />

            <div class="px-4 py-3 flex items-center justify-between gap-3">
              <span class="text-[11px] text-[#86868b] truncate">解析于 {{ formatTime(item.created_at) }}</span>
              <div class="flex items-center gap-2 shrink-0">
                <span class="text-[10px] font-medium px-2 py-1 rounded-full cursor-help"
                      :class="statusMeta(item.status).badge"
                      :title="statusTitle(item)">
                  {{ statusMeta(item.status).label }}
                </span>
                <button
                  @click.stop="handleDelete(item.id)"
                  :disabled="deletingId !== null"
                  title="删除这条记录"
                  class="w-7 h-7 rounded-lg bg-[#f5f5f7] text-[#86868b] hover:bg-red-50 hover:text-red-500
                         active:scale-[0.95] disabled:opacity-40 transition-all flex items-center justify-center"
                >
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round"
                          d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                  </svg>
                </button>
              </div>
            </div>
          </article>
        </div>

        <!-- Pagination -->
        <div v-if="items.length > 0" class="flex flex-col items-center gap-2 mt-10">
          <button
            v-if="hasMore"
            @click="loadMore"
            :disabled="loadingMore"
            class="px-6 py-2.5 bg-[#f5f5f7] text-[#1d1d1f] font-medium rounded-xl text-sm
                   hover:bg-[#e8e8ed] active:scale-[0.98]
                   disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            {{ loadingMore ? '加载中...' : '加载更多' }}
          </button>
          <p v-else class="text-xs text-[#86868b]">已显示全部 {{ total }} 条记录</p>
        </div>

      </div>
    </section>
  </div>
</template>
