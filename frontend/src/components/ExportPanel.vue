<template>
  <div class="flex flex-wrap gap-3">
    <button
      @click="exportFile('markdown')"
      class="flex items-center gap-2 px-5 py-2.5 rounded-xl border border-gray-200 bg-white text-sm font-medium text-apple-black hover:bg-gray-50 transition-colors"
    >
      <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
      导出 Markdown
    </button>
    <button
      @click="exportFile('pdf')"
      class="flex items-center gap-2 px-5 py-2.5 rounded-xl border border-gray-200 bg-white text-sm font-medium text-apple-black hover:bg-gray-50 transition-colors"
    >
      <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
      导出 PDF
    </button>
    <button
      @click="copyToClipboard"
      class="flex items-center gap-2 px-5 py-2.5 rounded-xl border border-gray-200 bg-white text-sm font-medium text-apple-black hover:bg-gray-50 transition-colors"
    >
      <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"/></svg>
      {{ copied ? '已复制' : '复制到剪贴板' }}
    </button>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { getExportUrl } from '../api'

const props = defineProps({
  taskId: String,
  result: Object,
  title: String,
})
const copied = ref(false)

function exportFile(format) {
  const url = getExportUrl(props.taskId, format)
  window.open(url, '_blank')
}

function copyToClipboard() {
  if (!props.result) return
  const text = [
    `# ${props.title || '视频总结'}`,
    '',
    '## 摘要',
    props.result.summary,
    '',
    ...(props.result.highlights?.length ? [
      '## 亮点',
      ...props.result.highlights.map(h => `- [${h.timestamp}] ${h.point}`),
      '',
    ] : []),
    ...(props.result.terms?.length ? [
      '## 术语解释',
      ...props.result.terms.map(t => `- **${t.term}**: ${t.explanation}`),
      '',
    ] : []),
    ...(props.result.qa?.length ? [
      '## 思考',
      ...props.result.qa.flatMap(q => [`### ${q.question}`, q.answer, '']),
    ] : []),
  ].join('\n')

  navigator.clipboard.writeText(text).then(() => {
    copied.value = true
    setTimeout(() => { copied.value = false }, 2000)
  })
}
</script>
