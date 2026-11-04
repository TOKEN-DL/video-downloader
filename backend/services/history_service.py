"""历史记录读写服务。

纯数据层：不依赖 FastAPI，不做网络 IO。JSON 字段在本层反序列化，
路由层只接触普通 dict / list。

表结构见 database/models.py —— 列已一次建齐，后续票据只往里写数据。
"""
import json
import logging
import os
from datetime import datetime

import config
from database import db
from database.models import HISTORY_LIST_COLUMNS

logger = logging.getLogger("history_service")

# 列表接口单页上限，防止一次拉爆内存
MAX_PAGE_SIZE = 100


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def upsert_parsed(url: str, video_info: dict, subtitle_lang: str | None = None) -> int:
    """解析成功后写入/更新记录，返回 record_id。

    同一 URL 重复解析 → 更新原记录（url 上的 UNIQUE 索引 + ON CONFLICT DO UPDATE），
    列表里不会出现重复条目。status 不在更新分支里改动：状态流转由 AI
    分析那张票负责，这里只负责「解析成功即建记录」。
    """
    conn = db.get_conn()
    now = _now()
    formats_json = json.dumps(video_info.get("formats") or [], ensure_ascii=False)

    conn.execute(
        """
        INSERT INTO history (
            url, title, author, platform, thumbnail, duration,
            formats_json, subtitle_lang, status, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'parsed', ?, ?)
        ON CONFLICT(url) DO UPDATE SET
            title         = excluded.title,
            author        = excluded.author,
            platform      = excluded.platform,
            thumbnail     = excluded.thumbnail,
            duration      = excluded.duration,
            formats_json  = excluded.formats_json,
            subtitle_lang = COALESCE(excluded.subtitle_lang, history.subtitle_lang),
            updated_at    = excluded.updated_at
        """,
        (
            url,
            video_info.get("title") or "",
            video_info.get("author") or "",
            video_info.get("platform") or "",
            video_info.get("thumbnail") or "",
            video_info.get("duration"),
            formats_json,
            subtitle_lang,
            now,
            now,
        ),
    )
    conn.commit()

    row = conn.execute("SELECT id FROM history WHERE url = ?", (url,)).fetchone()
    return row["id"]


def _loads(raw: str | None, default):
    """反序列化 JSON 列；内容坏了就退回默认值，不让整个接口 500。"""
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default


def get_record(record_id: int) -> dict | None:
    """取完整记录（含字幕 / AI 大字段）。记录不存在返回 None。"""
    conn = db.get_conn()
    row = conn.execute("SELECT * FROM history WHERE id = ?", (record_id,)).fetchone()
    if row is None:
        return None

    record = {key: row[key] for key in row.keys()}
    record["formats"] = _loads(record.pop("formats_json"), [])
    record["subtitle_data"] = _loads(record.pop("subtitle_json"), [])
    record["ai_result"] = _loads(record.pop("ai_result"), None)
    record["mindmap_markdown"] = record.pop("mindmap_md") or ""
    record["has_ai"] = record["status"] == "ai_done"
    return record


def _thumb_file_candidates(thumb_path: str) -> list[str]:
    """封面文件的可能位置。

    thumb_path 存的是相对路径，写入方（封面缓存那张票）可能记 '12.jpg'，
    也可能记 'thumbs/12.jpg'，两种写法都兜住，免得删不掉留下孤儿文件。
    绝对路径原样使用；相对路径只接受落在封面目录内的位置。
    """
    if not thumb_path:
        return []
    if os.path.isabs(thumb_path):
        return [thumb_path]

    base = os.path.abspath(config.HISTORY_THUMB_DIR)
    candidates = [
        os.path.join(base, os.path.basename(thumb_path)),
        os.path.join(base, thumb_path),
    ]
    safe = []
    for path in candidates:
        resolved = os.path.abspath(path)
        if resolved.startswith(base + os.sep):
            safe.append(resolved)
    return safe


def _remove_thumb_files(thumb_path: str) -> None:
    """删掉某条记录缓存的封面文件。删不掉只记日志，不影响删除记录本身。"""
    for path in _thumb_file_candidates(thumb_path):
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError as e:
            logger.warning(f"删除封面文件失败 ({path}): {e}")


def _sweep_thumb_dir() -> None:
    """清空记录后，封面目录里剩下的文件都是孤儿，一并清掉。"""
    base = config.HISTORY_THUMB_DIR
    if not os.path.isdir(base):
        return
    for name in os.listdir(base):
        path = os.path.join(base, name)
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError as e:
            logger.warning(f"删除封面文件失败 ({path}): {e}")


def delete_record(record_id: int) -> bool:
    """删除单条记录，并清掉它缓存的本地封面。记录不存在返回 False。"""
    conn = db.get_conn()
    row = conn.execute(
        "SELECT thumb_path FROM history WHERE id = ?", (record_id,)
    ).fetchone()
    if row is None:
        return False

    conn.execute("DELETE FROM history WHERE id = ?", (record_id,))
    conn.commit()
    _remove_thumb_files(row["thumb_path"])
    return True


def clear_records() -> int:
    """清空全部记录，并清掉所有本地封面文件。返回删除条数。"""
    conn = db.get_conn()
    rows = conn.execute("SELECT thumb_path FROM history").fetchall()
    conn.execute("DELETE FROM history")
    conn.commit()

    for row in rows:
        _remove_thumb_files(row["thumb_path"])
    _sweep_thumb_dir()
    return len(rows)


def list_records(
    page: int = 1,
    page_size: int | None = None,
    platform: str | None = None,
    keyword: str | None = None,
) -> dict:
    """分页查询历史记录。

    返回 {total, page, page_size, items}；items 刻意不含字幕 / AI 大字段，
    保证分页接口轻量。
    """
    conn = db.get_conn()

    page = max(1, int(page or 1))
    size = int(page_size or config.HISTORY_PAGE_SIZE_DEFAULT)
    size = max(1, min(size, MAX_PAGE_SIZE))

    where = []
    params = []
    if platform:
        where.append("platform = ?")
        params.append(platform)
    if keyword:
        where.append("(title LIKE ? OR author LIKE ? OR url LIKE ?)")
        params.extend([f"%{keyword}%"] * 3)
    clause = f"WHERE {' AND '.join(where)}" if where else ""

    total = conn.execute(
        f"SELECT COUNT(*) AS c FROM history {clause}", params
    ).fetchone()["c"]

    columns = ", ".join(HISTORY_LIST_COLUMNS)
    rows = conn.execute(
        f"SELECT {columns} FROM history {clause} "
        f"ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
        params + [size, (page - 1) * size],
    ).fetchall()

    items = []
    for row in rows:
        item = {key: row[key] for key in HISTORY_LIST_COLUMNS}
        item["has_ai"] = item["status"] == "ai_done"
        items.append(item)

    return {"total": total, "page": page, "page_size": size, "items": items}
