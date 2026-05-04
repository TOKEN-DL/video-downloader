const BASE = ''

export async function parseVideo(url) {
  const res = await fetch(`${BASE}/api/parse`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || '解析失败')
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
    throw new Error(err.detail || '下载失败')
  }
  return res.json()
}

export async function getDownloadStatus(taskId) {
  const res = await fetch(`${BASE}/api/download/status/${taskId}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || '查询失败')
  }
  return res.json()
}

export function getDownloadUrl(taskId) {
  return `${BASE}/api/download/file/${taskId}`
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
