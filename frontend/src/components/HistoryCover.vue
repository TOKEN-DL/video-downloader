<template>
  <!-- 视频封面卡块：列表页与详情页共用。 -->
  <div class="relative w-full aspect-video bg-gray-100 overflow-hidden">
    <!-- 封面优先读本地缓存，取不到自动回退远程代理图 -->
    <HistoryThumb :record="record" alt="" class="w-full h-full object-cover" />
    <div class="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent"></div>
    <div v-if="record.duration"
         class="absolute bottom-2 right-2 bg-black/70 text-white text-[10px] px-1.5 py-0.5 rounded-md backdrop-blur-sm">
      {{ formatDuration(record.duration) }}
    </div>
    <div v-if="record.platform"
         class="absolute top-2 left-2 bg-black/50 text-white text-[9px] px-2 py-0.5 rounded-full font-medium uppercase tracking-wider backdrop-blur-sm">
      {{ record.platform }}
    </div>
    <div class="absolute bottom-0 left-0 right-0 p-3 md:p-4">
      <h3 class="text-white font-semibold text-sm md:text-base leading-snug line-clamp-2 drop-shadow-md">
        {{ record.title }}
      </h3>
      <p v-if="record.author" class="text-white/70 text-[11px] md:text-xs mt-0.5 drop-shadow-sm">
        {{ record.author }}
      </p>
    </div>
  </div>
</template>

<script setup>
import HistoryThumb from './HistoryThumb.vue'
import { formatDuration } from '../api'

// record 形如历史记录对象：需要 thumbnail / thumb_path / duration / platform / title / author
defineProps({
  record: { type: Object, required: true },
})
</script>
