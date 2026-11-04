"""历史记录表结构。

表结构一次建齐：后续票据（AI 分析入库、字幕、封面缓存）只往这些列里写数据，
不再改表结构，因此整个功能不需要任何迁移逻辑。
"""

HISTORY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    url           TEXT    NOT NULL UNIQUE,        -- 归一化后的原始链接
    title         TEXT    NOT NULL DEFAULT '',
    author        TEXT    NOT NULL DEFAULT '',
    platform      TEXT    NOT NULL DEFAULT '',
    thumbnail     TEXT    NOT NULL DEFAULT '',     -- 远程封面 URL
    thumb_path    TEXT    NOT NULL DEFAULT '',     -- 本地缓存封面（相对路径）
    duration      REAL,
    formats_json  TEXT    NOT NULL DEFAULT '[]',   -- [{format_id,resolution,ext,filesize}]
    subtitle_lang TEXT,
    subtitle_json TEXT,                            -- [{time,text}]，带时间戳
    transcript    TEXT,                            -- 字幕纯文本
    ai_result     TEXT,                            -- {summary,highlights,terms,qa}
    mindmap_md    TEXT,                            -- markmap 兼容的 Markdown
    status        TEXT    NOT NULL DEFAULT 'parsed',  -- parsed | ai_done | ai_failed
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
HISTORY_LIST_COLUMNS = (
    "id",
    "title",
    "author",
    "platform",
    "thumbnail",
    "thumb_path",
    "duration",
    "status",
    "created_at",
    "updated_at",
)
