<template>
  <div class="relative">
    <!-- 工具栏 -->
    <div class="flex items-center justify-end gap-2 mb-3">
      <button @click="handleFit" class="toolbar-btn">适应</button>
      <button @click="handleExportSvg" class="toolbar-btn">导出 SVG</button>
      <button @click="handleExportPng" class="toolbar-btn">导出 PNG</button>
      <button @click="toggleFullscreen" class="toolbar-btn">{{ isFullscreen ? '退出全屏' : '全屏' }}</button>
    </div>

    <!-- SVG 容器 -->
    <div ref="wrapper" class="w-full border border-gray-100 rounded-2xl bg-white overflow-hidden"
      :class="isFullscreen ? 'fixed inset-0 z-50 rounded-none border-none' : ''">
      <svg ref="svgEl" class="w-full h-full" style="min-height: 500px"></svg>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { Transformer } from 'markmap-lib'
import { Markmap } from 'markmap-view'

const props = defineProps({ markdown: String })

const svgEl = ref(null)
const wrapper = ref(null)
let mm = null
const isFullscreen = ref(false)

function renderMap() {
  if (!props.markdown || !svgEl.value) return
  try {
    svgEl.value.innerHTML = ''
    const transformer = new Transformer()
    const { root } = transformer.transform(props.markdown)
    mm = Markmap.create(svgEl.value, { autoFit: true }, root)
  } catch (e) {
    console.warn('思维导图渲染失败:', e)
    if (svgEl.value) {
      svgEl.value.innerHTML = ''
    }
  }
}

function handleFit() {
  if (mm) mm.fit()
}

function toggleFullscreen() {
  if (!wrapper.value) return
  if (!isFullscreen.value) {
    wrapper.value.requestFullscreen?.()
  } else {
    document.exitFullscreen?.()
  }
}

function onFullscreenChange() {
  isFullscreen.value = !!document.fullscreenElement
  nextTick(() => { if (mm) mm.fit() })
}

function handleExportSvg() {
  if (!svgEl.value) return
  const str = new XMLSerializer().serializeToString(svgEl.value)
  const blob = new Blob([str], { type: 'image/svg+xml;charset=utf-8' })
  download(blob, 'mindmap.svg')
}

function handleExportPng() {
  if (!svgEl.value) return
  const str = new XMLSerializer().serializeToString(svgEl.value)
  const rect = svgEl.value.getBoundingClientRect()
  const canvas = document.createElement('canvas')
  canvas.width = rect.width * 2
  canvas.height = rect.height * 2
  const ctx = canvas.getContext('2d')
  ctx.fillStyle = '#fff'
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  const img = new Image()
  const url = URL.createObjectURL(new Blob([str], { type: 'image/svg+xml;charset=utf-8' }))
  img.onload = () => {
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
    URL.revokeObjectURL(url)
    canvas.toBlob((b) => { if (b) download(b, 'mindmap.png') }, 'image/png')
  }
  img.src = url
}

function download(blob, name) {
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = name
  a.click()
  URL.revokeObjectURL(a.href)
}

onMounted(() => {
  renderMap()
  document.addEventListener('fullscreenchange', onFullscreenChange)
})

onBeforeUnmount(() => {
  document.removeEventListener('fullscreenchange', onFullscreenChange)
})

watch(() => props.markdown, renderMap)
</script>

<style scoped>
.toolbar-btn {
  font-size: 12px;
  padding: 6px 10px;
  border-radius: 8px;
  color: #0071e3;
  border: none;
  background: none;
  cursor: pointer;
  transition: background 0.15s;
}
.toolbar-btn:hover {
  background: rgba(0, 113, 227, 0.08);
}
:deep(.markmap-foreign) { display: inline-block !important; }
:deep(foreignObject) { overflow: visible !important; }
:deep(foreignObject div) { font: 300 14px/20px sans-serif; color: #333; }
</style>
