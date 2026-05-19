<template>
  <div class="flex flex-col h-[400px]">
    <!-- 消息列表 -->
    <div ref="messageList" class="flex-1 overflow-y-auto space-y-3 pr-1 mb-3">
      <div
        v-for="(msg, i) in messages"
        :key="i"
        class="flex"
        :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
      >
        <div
          class="max-w-[80%] px-4 py-2.5 rounded-2xl text-[14px] leading-relaxed"
          :class="msg.role === 'user'
            ? 'bg-apple-blue text-white rounded-br-sm'
            : 'bg-gray-100 text-apple-black rounded-bl-sm'"
        >
          {{ msg.content }}
        </div>
      </div>
      <div v-if="loading" class="flex justify-start">
        <div class="bg-gray-100 rounded-2xl rounded-bl-sm px-4 py-3">
          <div class="flex gap-1">
            <span class="w-2 h-2 rounded-full bg-apple-gray animate-bounce" style="animation-delay:0ms"></span>
            <span class="w-2 h-2 rounded-full bg-apple-gray animate-bounce" style="animation-delay:150ms"></span>
            <span class="w-2 h-2 rounded-full bg-apple-gray animate-bounce" style="animation-delay:300ms"></span>
          </div>
        </div>
      </div>
    </div>
    <!-- 输入框 -->
    <div class="flex gap-2">
      <input
        v-model="input"
        @keydown.enter="send"
        :disabled="loading"
        placeholder="针对视频内容提问..."
        class="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 bg-white text-sm focus:outline-none focus:border-apple-blue transition-colors"
      />
      <button
        @click="send"
        :disabled="loading || !input.trim()"
        class="px-4 py-2.5 bg-apple-blue text-white rounded-xl text-sm font-medium disabled:opacity-40 hover:bg-blue-600 transition-colors"
      >
        发送
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, watch } from 'vue'

const props = defineProps({
  messages: Array,
  loading: Boolean,
})
const emit = defineEmits(['send'])
const input = ref('')
const messageList = ref(null)

function send() {
  if (!input.value.trim() || props.loading) return
  emit('send', input.value.trim())
  input.value = ''
}

watch(() => props.messages.length, async () => {
  await nextTick()
  if (messageList.value) {
    messageList.value.scrollTop = messageList.value.scrollHeight
  }
})
</script>
