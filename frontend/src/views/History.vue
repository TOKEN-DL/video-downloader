<script setup>
import { onMounted } from 'vue'
import { useHistory } from '../composables/useHistory'
import HistoryThumb from '../components/HistoryThumb.vue'
import { formatDuration } from '../api'

const {
  items, total, hasMore,
  loading, loadingMore, error,
  load, loadMore,
} = useHistory()

// 状态徽标：parsed=已解析，ai_done=AI 已总结，ai_failed=AI 失败
const STATUS_META = {
  parsed: { label: '已解析', badge: 'bg-gray-100 text-[#86868b]' },
  ai_done: { label: 'AI 已总结', badge: 'bg-green-50 text-green-600' },
  ai_failed: { label: 'AI 失败', badge: 'bg-orange-50 text-orange-600' },
}

function statusMeta(status) {
  return STATUS_META[status] || STATUS_META.parsed
}

// 后端存的是 "YYYY-MM-DD HH:MM:SS"，展示到分钟即可
function formatTime(value) {
  return value ? String(value).slice(0, 16) : ''
}

onMounted(load)
</script>

<template>
  <div class="min-h-screen bg-white flex flex-col font-sans">

    <!-- ═══ Navbar ═══ -->
    <nav class="sticky top-0 z-50 glass-card">
      <div class="max-w-[1200px] mx-auto px-6 h-11 flex items-center justify-between">
        <router-link to="/" class="flex items-center gap-2 group">
          <div class="w-7 h-7 bg-[#0071e3] rounded-lg flex items-center justify-center
                      group-hover:bg-[#0077ed] transition-colors">
            <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" stroke-width="2.2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round"
                    d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
            </svg>
          </div>
          <span class="font-semibold text-[#1d1d1f] text-sm tracking-tight">时雨视频分析</span>
        </router-link>

        <div class="flex items-center gap-7 text-xs text-[#86868b]">
          <router-link to="/history" class="text-[#1d1d1f] font-medium">历史记录</router-link>
          <router-link to="/" class="hover:text-[#1d1d1f] transition-colors">返回首页</router-link>
        </div>
      </div>
    </nav>

    <!-- ═══ Content ═══ -->
    <section class="flex-1 px-6 py-10 md:py-14">
      <div class="max-w-[1200px] mx-auto">

        <!-- Header -->
        <div class="flex items-baseline justify-between mb-8">
          <h1 class="text-[#1d1d1f] text-2xl md:text-[32px] font-semibold tracking-tight">历史记录</h1>
          <span v-if="total > 0" class="text-xs text-[#86868b] tabular-nums">共 {{ total }} 条</span>
        </div>

        <!-- Error -->
        <p v-if="error" class="mb-6 text-red-500 text-sm flex items-center justify-center gap-1.5">
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
          </svg>
          {{ error }}
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
            class="card-hover bg-white rounded-2xl border border-gray-100 shadow-lg overflow-hidden"
          >
            <div class="relative w-full aspect-video bg-gray-100 overflow-hidden">
              <!-- 封面优先读本地缓存，取不到自动回退远程代理图 -->
              <HistoryThumb :record="item" alt="" class="w-full h-full object-cover" />
              <div class="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent"></div>
              <div v-if="item.duration"
                   class="absolute bottom-2 right-2 bg-black/70 text-white text-[10px] px-1.5 py-0.5 rounded-md backdrop-blur-sm">
                {{ formatDuration(item.duration) }}
              </div>
              <div v-if="item.platform"
                   class="absolute top-2 left-2 bg-black/50 text-white text-[9px] px-2 py-0.5 rounded-full font-medium uppercase tracking-wider backdrop-blur-sm">
                {{ item.platform }}
              </div>
              <div class="absolute bottom-0 left-0 right-0 p-3 md:p-4">
                <h3 class="text-white font-semibold text-sm md:text-base leading-snug line-clamp-2 drop-shadow-md">
                  {{ item.title }}
                </h3>
                <p v-if="item.author" class="text-white/70 text-[11px] md:text-xs mt-0.5 drop-shadow-sm">
                  {{ item.author }}
                </p>
              </div>
            </div>

            <div class="px-4 py-3 flex items-center justify-between gap-3">
              <span class="text-[11px] text-[#86868b] truncate">解析于 {{ formatTime(item.created_at) }}</span>
              <span class="shrink-0 text-[10px] font-medium px-2 py-1 rounded-full"
                    :class="statusMeta(item.status).badge">
                {{ statusMeta(item.status).label }}
              </span>
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
