<template>
  <div v-if="result" class="space-y-5">
    <!-- 摘要 -->
    <div class="rounded-2xl bg-white/80 backdrop-blur-sm p-5 shadow-sm border border-gray-100">
      <h3 class="text-sm font-semibold text-apple-gray uppercase tracking-wider mb-3">摘要</h3>
      <p class="text-apple-black leading-relaxed text-[15px]">{{ result.summary }}</p>
    </div>

    <!-- 亮点 -->
    <div v-if="result.highlights?.length" class="rounded-2xl bg-white/80 backdrop-blur-sm p-5 shadow-sm border border-gray-100">
      <h3 class="text-sm font-semibold text-apple-gray uppercase tracking-wider mb-3">亮点</h3>
      <ul class="space-y-2.5">
        <li v-for="(h, i) in result.highlights" :key="i" class="flex items-start gap-3">
          <span class="shrink-0 mt-0.5 inline-flex items-center justify-center w-12 h-5 rounded-full bg-apple-blue/10 text-apple-blue text-xs font-medium">
            {{ h.timestamp }}
          </span>
          <span class="text-apple-black text-[15px] leading-relaxed">{{ h.point }}</span>
        </li>
      </ul>
    </div>

    <!-- 术语解释 -->
    <div v-if="result.terms?.length" class="rounded-2xl bg-white/80 backdrop-blur-sm p-5 shadow-sm border border-gray-100">
      <h3 class="text-sm font-semibold text-apple-gray uppercase tracking-wider mb-3">术语解释</h3>
      <div class="space-y-2.5">
        <div v-for="(t, i) in result.terms" :key="i">
          <span class="font-semibold text-apple-black">{{ t.term }}</span>
          <span class="text-apple-gray ml-1">— {{ t.explanation }}</span>
        </div>
      </div>
    </div>

    <!-- 思考问答 -->
    <div v-if="result.qa?.length" class="rounded-2xl bg-white/80 backdrop-blur-sm p-5 shadow-sm border border-gray-100">
      <h3 class="text-sm font-semibold text-apple-gray uppercase tracking-wider mb-3">思考</h3>
      <div class="space-y-4">
        <div v-for="(q, i) in result.qa" :key="i">
          <button
            class="w-full text-left flex items-start gap-2 group"
            @click="toggleQA(i)"
          >
            <span class="shrink-0 mt-0.5 text-apple-blue font-bold text-sm">{{ i + 1 }}.</span>
            <span class="text-apple-black text-[15px] font-medium group-hover:text-apple-blue transition-colors">{{ q.question }}</span>
            <svg class="shrink-0 mt-1 w-4 h-4 text-apple-gray transition-transform" :class="{ 'rotate-180': openQA[i] }" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
          </button>
          <div v-if="openQA[i]" class="mt-2 ml-6 text-apple-gray text-[14px] leading-relaxed">
            {{ q.answer }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive } from 'vue'
defineProps({ result: Object })
const openQA = reactive({})
function toggleQA(i) { openQA[i] = !openQA[i] }
</script>
