"""历史记录详情 / 删除 / 清空 的接口级测试。

唯一接缝是 HTTP API：打真实应用、真实 SQLite，只把外部世界（视频解析）打桩。
封面文件属于运行期产物，测试里指向临时目录，绝不碰真实的 backend/history/。
"""
from database import db
import config
import os
import sqlite3


def _rows():
    return db.get_conn().execute("SELECT * FROM history").fetchall()


def test_history_detail_returns_video_info_and_formats(client, stub_parse):
    """详情接口返回该视频的封面、标题、作者、平台、时长与可用清晰度。"""
    stub_parse.result = {
        **stub_parse.result,
        "formats": [
            {"format_id": "30016", "resolution": "720p", "ext": "mp4", "filesize": 12345678},
            {"format_id": "30080", "resolution": "1080p", "ext": "mp4", "filesize": 22345678},
        ],
    }
    parsed = client.post(
        "/api/parse", json={"url": "https://www.bilibili.com/video/BV1xx"}
    ).json()

    resp = client.get(f"/api/history/{parsed['history_id']}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == parsed["history_id"]
    assert body["url"] == "https://www.bilibili.com/video/BV1xx"
    assert body["title"] == "示例视频标题"
    assert body["author"] == "示例作者"
    assert body["platform"] == "bilibili"
    assert body["duration"] == 754.0
    assert body["thumbnail"] == "https://example.com/cover.jpg"
    assert body["formats"] == [
        {"format_id": "30016", "resolution": "720p", "ext": "mp4", "filesize": 12345678},
        {"format_id": "30080", "resolution": "1080p", "ext": "mp4", "filesize": 22345678},
    ]


def test_history_detail_of_missing_record_reports_not_found(client):
    """访问不存在的记录 ID 时返回 404 + 「记录不存在」。"""
    resp = client.get("/api/history/9999")

    assert resp.status_code == 404
    assert resp.json()["detail"] == "记录不存在"


def test_delete_history_record_removes_it_from_list(client, stub_parse):
    """删除单条记录后，它立刻从历史列表里消失。"""
    parsed = client.post(
        "/api/parse", json={"url": "https://www.bilibili.com/video/BV1xx"}
    ).json()

    resp = client.delete(f"/api/history/{parsed['history_id']}")

    assert resp.status_code == 200
    assert resp.json() == {"deleted": True}

    body = client.get("/api/history").json()
    assert body["total"] == 0
    assert body["items"] == []
    assert _rows() == []


def test_deleted_record_stays_gone_after_restart(client, stub_parse, temp_db):
    """删掉的记录不会复活：换个新连接读（相当于后端重启）依然不在。"""
    parsed = client.post(
        "/api/parse", json={"url": "https://www.bilibili.com/video/BV1xx"}
    ).json()
    client.delete(f"/api/history/{parsed['history_id']}")

    conn = sqlite3.connect(temp_db)
    try:
        rows = conn.execute("SELECT id FROM history").fetchall()
    finally:
        conn.close()
    assert rows == []

    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as restarted:
        body = restarted.get("/api/history").json()

    assert body["total"] == 0
    assert body["items"] == []


def test_delete_missing_record_reports_not_found(client):
    """删除不存在的记录返回 404 + 「记录不存在」，不会静默成功。"""
    resp = client.delete("/api/history/9999")

    assert resp.status_code == 404
    assert resp.json()["detail"] == "记录不存在"


def test_clear_all_history_records_empties_list(client, stub_parse):
    """清空全部记录后，列表与库里都不剩东西。"""
    for i in range(3):
        stub_parse.result = {**stub_parse.result, "title": f"视频{i}"}
        client.post("/api/parse", json={"url": f"https://example.com/video/{i}"})

    resp = client.delete("/api/history")

    assert resp.status_code == 200
    assert resp.json() == {"deleted": 3}

    body = client.get("/api/history").json()
    assert body["total"] == 0
    assert body["items"] == []
    assert _rows() == []


def _cache_cover(record_id: int, filename: str | None = None) -> str:
    """造一个缓存封面文件并把 thumb_path 写回记录。

    封面本身由封面缓存那张票负责下载，本票只负责删除时清理，
    所以这里直接摆好文件，模拟那张票的产物。
    """
    os.makedirs(config.HISTORY_THUMB_DIR, exist_ok=True)
    filename = filename or f"{record_id}.jpg"
    path = os.path.join(config.HISTORY_THUMB_DIR, filename)
    with open(path, "wb") as f:
        f.write(b"fake-jpeg-bytes")

    conn = db.get_conn()
    conn.execute(
        "UPDATE history SET thumb_path = ? WHERE id = ?", (f"thumbs/{filename}", record_id)
    )
    conn.commit()
    return path


def test_deleting_record_removes_its_cached_cover_file(client, stub_parse):
    """删除记录时，它缓存的封面文件一并被删掉，不留孤儿文件。"""
    parsed = client.post(
        "/api/parse", json={"url": "https://www.bilibili.com/video/BV1xx"}
    ).json()
    thumb = _cache_cover(parsed["history_id"])
    assert os.path.exists(thumb)

    resp = client.delete(f"/api/history/{parsed['history_id']}")

    assert resp.status_code == 200
    assert not os.path.exists(thumb)


def test_clearing_all_records_removes_cached_cover_files(client, stub_parse):
    """清空全部时，每条记录缓存的封面文件都被清掉。"""
    ids = []
    for i in range(2):
        parsed = client.post(
            "/api/parse", json={"url": f"https://example.com/video/{i}"}
        ).json()
        ids.append(parsed["history_id"])
    thumbs = [_cache_cover(record_id) for record_id in ids]

    resp = client.delete("/api/history")

    assert resp.status_code == 200
    assert resp.json() == {"deleted": 2}
    for thumb in thumbs:
        assert not os.path.exists(thumb)


def test_deleting_one_record_keeps_other_records_covers(client, stub_parse):
    """删掉一条记录不会误伤别的记录缓存的封面。"""
    first = client.post(
        "/api/parse", json={"url": "https://example.com/video/1"}
    ).json()
    second = client.post(
        "/api/parse", json={"url": "https://example.com/video/2"}
    ).json()
    first_thumb = _cache_cover(first["history_id"])
    second_thumb = _cache_cover(second["history_id"])

    client.delete(f"/api/history/{first['history_id']}")

    assert not os.path.exists(first_thumb)
    assert os.path.exists(second_thumb)
