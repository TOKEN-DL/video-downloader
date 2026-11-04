<template>
  <img v-if="src" :src="src" :alt="alt" @error="onError" />
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { getHistoryThumbUrl, proxyImageUrl } from '../api'

// 历史记录封面：优先本地缓存（封面 URL 带签名会过期），
// 本地取不到时回退远程代理图，两边都没有就不渲染，避免出现裂图。
const props = defineProps({
  record: { type: Object, required: true },
  alt: { type: String, default: '' },
})

const useRemote = ref(false)
const broken = ref(false)

const localUrl = computed(() =>
  props.record.thumb_path ? getHistoryThumbUrl(props.record.id) : ''
)
const remoteUrl = computed(() =>
  props.record.thumbnail ? proxyImageUrl(props.record.thumbnail) : ''
)
const src = computed(() => {
  if (broken.value) return ''
  if (useRemote.value) return remoteUrl.value
  return localUrl.value || remoteUrl.value
})

// 换一条记录时重新从本地封面开始试
watch(() => props.record.id, () => {
  useRemote.value = false
  broken.value = false
})

function onError() {
  if (!useRemote.value && localUrl.value && remoteUrl.value) {
    useRemote.value = true // 本地封面还没有 / 已失效 → 回退远程
    return
  }
  broken.value = true // 远程也没有 → 干脆不显示
}
</script>
