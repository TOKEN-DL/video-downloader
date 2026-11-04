"""历史记录表结构。

表结构一次建齐：后续票据（AI 分析入库、字幕、封面缓存）只往这些列里写数据，
不再改表结构，因此整个功能不需要任何迁移逻辑。
"""

# 历史记录状态值：后端只此一处定义，改状态语义只需要改这里。
# 与前端 frontend/src/constants/history.js 的 HISTORY_STATUS 一一对应。
STATUS_PARSED = "parsed"
STATUS_AI_DONE = "ai_done"
STATUS_AI_FAILED = "ai_failed"

# 建表语句用 f-string 把状态默认值插进来（下面几行的列注释刻意不带花括号，
# 否则会被 f-string 当成占位符解析）。
HISTORY_TABLE_SQL = f"""
CREATE TABLE IF NOT EXISTS history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    url           TEXT    NOT NULL UNIQUE,        -- 归一化后的原始链接
    title         TEXT    NOT NULL DEFAULT '',
    author        TEXT    NOT NULL DEFAULT '',
    platform      TEXT    NOT NULL DEFAULT '',
    thumbnail     TEXT    NOT NULL DEFAULT '',     -- 远程封面 URL
    thumb_path    TEXT    NOT NULL DEFAULT '',     -- 本地缓存封面（相对路径）
    duration      REAL,
    formats_json  TEXT    NOT NULL DEFAULT '[]',   -- 格式数组：format_id / resolution / ext / filesize
    subtitle_lang TEXT,
    subtitle_json TEXT,                            -- 字幕数组：time / text，带时间戳
    transcript    TEXT,                            -- 字幕纯文本
    ai_result     TEXT,                            -- AI 结果对象：summary / highlights / terms / qa
    mindmap_md    TEXT,                            -- markmap 兼容的 Markdown
    status        TEXT    NOT NULL DEFAULT '{STATUS_PARSED}',  -- parsed | ai_done | ai_failed
    error         TEXT,
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL
)
"""

HISTORY_INDEX_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_history_created_at ON history (created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_history_status ON history (status)",
)

# 列表接口返回的列：刻意不含字幕 / AI 大字段，保证分页接口轻量。
# error 只是一句失败原因（AI 失败时才有），列表页要靠它 hover 显示失败原因，
# 体积可以忽略，所以列在白名单里。
HISTORY_LIST_COLUMNS = (
    "id",
    "title",
    "author",
    "platform",
    "thumbnail",
    "thumb_path",
    "duration",
    "status",
    "error",
    "created_at",
    "updated_at",
)
