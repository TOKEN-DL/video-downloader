"""历史记录读写服务。

纯数据层：不依赖 FastAPI，不做网络 IO。JSON 字段在本层反序列化，
路由层只接触普通 dict / list。

表结构见 database/models.py —— 列已一次建齐，后续票据只往里写数据。
"""
import json
import logging
import re
from datetime import datetime

import config
from database import db
from database.models import (
    HISTORY_LIST_COLUMNS,
    STATUS_AI_DONE,
    STATUS_AI_FAILED,
    STATUS_PARSED,
)
from services import thumb_service

logger = logging.getLogger("history_service")

# 列表接口单页上限，防止一次拉爆内存
MAX_PAGE_SIZE = 100


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


_RESOLUTION_RE = re.compile(r"(\d+)")


def _resolution_height(resolution) -> int | None:
    """把分辨率标签解析成像素高度；解析不出来（如抖音的 'best'）返回 None。"""
    text = str(resolution or "").strip().lower()
    if not text:
        return None
    if "x" in text:  # 1920x1080 → 取高度那一半
        text = text.rsplit("x", 1)[-1]
    m = _RESOLUTION_RE.search(text)
    return int(m.group(1)) if m else None


def pick_best_format(formats: list) -> str:
    """挑分辨率最高的一档；分辨率没法比较（如抖音的 'best'）时取第一档。

    详情页的默认清晰度与「不指定清晰度」的重新下载都用它，
    前端直接消费后端算好的结果，不再各写一套挑选逻辑。
    """
    best_id = ""
    best_height = -1
    for fmt in formats or []:
        if not isinstance(fmt, dict):
            continue
        format_id = str(fmt.get("format_id") or "").strip()
        if not format_id:
            continue
        height = _resolution_height(fmt.get("resolution"))
        if height is None:
            # 高度不可比：先占个位，遇到可比的就让位
            if not best_id:
                best_id = format_id
            continue
        if height > best_height:
            best_height = height
            best_id = format_id
    return best_id


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
        f"""
        INSERT INTO history (
            url, title, author, platform, thumbnail, duration,
            formats_json, subtitle_lang, status, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, '{STATUS_PARSED}', ?, ?)
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
    record["has_ai"] = record["status"] == STATUS_AI_DONE
    # 默认清晰度：记录里分辨率最高的一档。详情页与「不指定清晰度」的下载都用它，
    # 前端不必再自己实现一遍挑选逻辑。
    record["default_format_id"] = pick_best_format(record.get("formats") or [])
    return record


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
        item["has_ai"] = item["status"] == STATUS_AI_DONE
        items.append(item)

    return {"total": total, "page": page, "page_size": size, "items": items}


def attach_ai_result(
    record_id: int,
    subtitle_data: list | None,
    transcript: str | None,
    ai_result: dict | None,
    mindmap_md: str | None,
) -> bool:
    """AI 总结成功后把分析数据补写到记录上，status 变为 'ai_done'。

    新一轮 AI 成功 = 覆盖写入：同一 URL 通常就是同一个视频，
    旧的分析结果没有保留价值，但状态与错误文案要一起刷新干净。
    """
    conn = db.get_conn()
    cursor = conn.execute(
        f"""
        UPDATE history SET
            subtitle_json = ?,
            transcript    = ?,
            ai_result     = ?,
            mindmap_md    = ?,
            status        = '{STATUS_AI_DONE}',
            error         = NULL,
            updated_at    = ?
        WHERE id = ?
        """,
        (
            json.dumps(subtitle_data or [], ensure_ascii=False),
            transcript,
            json.dumps(ai_result or {}, ensure_ascii=False),
            mindmap_md or "",
            _now(),
            record_id,
        ),
    )
    conn.commit()
    return cursor.rowcount > 0


def mark_ai_failed(record_id: int, error: str) -> bool:
    """AI 总结失败时标记 status='ai_failed' 并记录失败原因。

    刻意不清空已有的 AI 数据：同一个 URL 一般就是同一个视频，
    之前跑出来的结果依然成立，不能因为一次失败就让人白跑一遍。
    """
    conn = db.get_conn()
    cursor = conn.execute(
        f"UPDATE history SET status = '{STATUS_AI_FAILED}', error = ?, updated_at = ? WHERE id = ?",
        (error, _now(), record_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def get_record_by_url(url: str) -> int | None:
    """按 url 取记录 ID（AI 总结没带 history_id 时的兜底）。找不到返回 None。"""
    if not url:
        return None
    conn = db.get_conn()
    row = conn.execute(
        "SELECT id FROM history WHERE url = ? ORDER BY updated_at DESC, id DESC LIMIT 1",
        (url.strip(),),
    ).fetchone()
    return row["id"] if row else None


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
