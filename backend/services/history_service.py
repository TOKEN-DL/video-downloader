"""历史记录读写服务。

纯数据层：不依赖 FastAPI，不做网络 IO。JSON 字段在本层反序列化，
路由层只接触普通 dict / list。

表结构见 database/models.py —— 列已一次建齐，后续票据只往里写数据。
"""
import json
import logging
from datetime import datetime

import config
from database import db
from database.models import HISTORY_LIST_COLUMNS
from services import thumb_service

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


def set_thumb_path(record_id: int, thumb_path: str) -> bool:
    """回写本地封面相对路径（封面下载成功后调用）。

    下载失败时 thumb_path 留空，前端回退远程封面代理图。
    """
    conn = db.get_conn()
    conn.execute(
        "UPDATE history SET thumb_path = ?, updated_at = ? WHERE id = ?",
        (thumb_path, _now(), record_id),
    )
    conn.commit()
    return True


def delete_thumb(record_id: int) -> bool:
    """删除单条记录的本地封面文件。

    与记录删除解耦，供删除流程直接调用；记录本身已不存在时也照删文件。
    """
    conn = db.get_conn()
    row = conn.execute(
        "SELECT thumb_path FROM history WHERE id = ?", (record_id,)
    ).fetchone()
    stored = row["thumb_path"] if row else None
    return thumb_service.delete_thumb(record_id, stored)


def clear_thumbs() -> int:
    """删除全部本地封面文件，返回删除数量。"""
    return thumb_service.clear_thumbs()


def delete_record(record_id: int) -> bool:
    """删除单条记录，并清理它对应的本地封面文件。

    返回是否真的删掉了记录（记录不存在返回 False）。
    """
    conn = db.get_conn()
    row = conn.execute(
        "SELECT thumb_path FROM history WHERE id = ?", (record_id,)
    ).fetchone()
    if row is None:
        return False

    conn.execute("DELETE FROM history WHERE id = ?", (record_id,))
    conn.commit()
    thumb_service.delete_thumb(record_id, row["thumb_path"])
    return True


def clear_records() -> int:
    """清空全部记录，并清理所有本地封面文件。返回删除的记录数。"""
    conn = db.get_conn()
    cursor = conn.execute("DELETE FROM history")
    conn.commit()
    deleted = cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0
    clear_thumbs()
    return deleted
