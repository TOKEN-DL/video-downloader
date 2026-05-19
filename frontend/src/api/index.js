const BASE = ''

function _extractDetail(err) {
  if (!err || !err.detail) return ''
  if (typeof err.detail === 'string') return err.detail
  if (Array.isArray(err.detail)) {
    return err.detail.map(e => e.msg || String(e)).join('; ')
  }
  return JSON.stringify(err.detail)
}

export async function parseVideo(url) {
  const res = await fetch(`${BASE}/api/parse`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(_extractDetail(err) || '解析失败')
  }
  return res.json()
}

export async function startDownload(url, formatId) {
  const res = await fetch(`${BASE}/api/download`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, format_id: formatId }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(_extractDetail(err) || '下载失败')
  }
  return res.json()
}

export async function getDownloadStatus(taskId) {
  const res = await fetch(`${BASE}/api/download/status/${taskId}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(_extractDetail(err) || '查询失败')
  }
  return res.json()
}

export function getDownloadUrl(taskId) {
  return `${BASE}/api/download/file/${taskId}`
}

export function proxyImageUrl(url) {
  if (!url) return ''
  return `${BASE}/api/proxy/image?${new URLSearchParams({ url })}`
}

export function formatFileSize(bytes) {
  if (!bytes) return ''
  if (bytes < 1024) return bytes + 'B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB'
  return (bytes / 1024 / 1024).toFixed(1) + 'MB'
}

export function formatDuration(seconds) {
  if (!seconds) return ''
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

// ============ AI Summarization ============

export async function startSummarize(url, subtitleLang) {
  const res = await fetch(`${BASE}/api/ai/summarize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, subtitle_lang: subtitleLang || null }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(_extractDetail(err) || 'AI 总结启动失败')
  }
  return res.json()
}

export async function getSummarizeStatus(taskId) {
  const res = await fetch(`${BASE}/api/ai/summarize/status/${taskId}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(_extractDetail(err) || '查询失败')
  }
  return res.json()
}

export async function sendChatMessage(messages, transcriptContext) {
  const res = await fetch(`${BASE}/api/ai/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url: '', messages, transcript_context: transcriptContext }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(_extractDetail(err) || 'AI 对话失败')
  }
  return res.json()
}

export function getExportUrl(taskId, format) {
  return `${BASE}/api/ai/export/${taskId}?format=${format}`
}
