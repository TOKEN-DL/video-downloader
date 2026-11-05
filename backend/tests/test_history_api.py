"""历史记录接口级测试。

唯一接缝是 HTTP API：打真实应用，验证「解析 → 落库 → 列表可见」这条链路。
"""
import config
import sqlite3

from database import db


def _rows():
    return db.get_conn().execute("SELECT * FROM history").fetchall()


def test_parse_creates_history_record(client, stub_parse):
    """解析成功后该视频立刻入库，返回值带上 history_id。"""
    resp = client.post("/api/parse", json={"url": "https://www.bilibili.com/video/BV1xx"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "示例视频标题"
    assert body["history_id"] is not None

    rows = _rows()
    assert len(rows) == 1
    row = rows[0]
    assert row["url"] == "https://www.bilibili.com/video/BV1xx"
    assert row["title"] == "示例视频标题"
    assert row["author"] == "示例作者"
    assert row["platform"] == "bilibili"
    assert row["duration"] == 754.0
    assert row["thumbnail"] == "https://example.com/cover.jpg"
    assert row["status"] == "parsed"


def test_history_list_shows_parsed_video(client, stub_parse):
    """解析过的视频能在历史列表里查到，字段齐全。"""
    client.post("/api/parse", json={"url": "https://www.bilibili.com/video/BV1xx"})

    resp = client.get("/api/history")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert len(body["items"]) == 1

    item = body["items"][0]
    assert item["title"] == "示例视频标题"
    assert item["author"] == "示例作者"
    assert item["platform"] == "bilibili"
    assert item["duration"] == 754.0
    assert item["thumbnail"] == "https://example.com/cover.jpg"
    assert item["status"] == "parsed"
    assert item["has_ai"] is False
    assert item["created_at"]
    assert item["updated_at"]


def test_same_url_parsed_twice_updates_single_row(client, stub_parse):
    """同一个链接解析两次，历史记录里仍然只有一条（更新而非新增）。"""
    url = "https://www.bilibili.com/video/BV1xx"
    client.post("/api/parse", json={"url": url})

    stub_parse.result = {**stub_parse.result, "title": "改过的标题", "author": "改过的作者"}
    resp = client.post("/api/parse", json={"url": url})
    assert resp.status_code == 200

    rows = _rows()
    assert len(rows) == 1
    assert rows[0]["title"] == "改过的标题"
    assert rows[0]["author"] == "改过的作者"

    body = client.get("/api/history").json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == "改过的标题"


def test_parse_survives_history_write_failure(client, stub_parse, tmp_path, monkeypatch, caplog):
    """落库失败（如磁盘满）时解析结果仍正常返回，只记日志，不阻断主流程。"""
    # 让数据库目录建不出来，模拟磁盘满 / 权限不足
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setattr(config, "DB_PATH", str(blocker / "history.db"))

    resp = client.post("/api/parse", json={"url": "https://www.bilibili.com/video/BV1xx"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "示例视频标题"
    assert "history_id" not in body
    assert any("历史记录落库失败" in record.message for record in caplog.records)


def test_history_list_paginates_newest_first(client, stub_parse):
    """列表分页可用：页尾「加载更多」能按页追加，最新的排在最前。"""
    for i in range(3):
        stub_parse.result = {**stub_parse.result, "title": f"视频{i}"}
        client.post("/api/parse", json={"url": f"https://example.com/video/{i}"})

    first = client.get("/api/history", params={"page": 1, "page_size": 2}).json()
    assert first["total"] == 3
    assert first["page"] == 1
    assert first["page_size"] == 2
    assert [item["title"] for item in first["items"]] == ["视频2", "视频1"]

    second = client.get("/api/history", params={"page": 2, "page_size": 2}).json()
    assert second["total"] == 3
    assert second["page"] == 2
    assert [item["title"] for item in second["items"]] == ["视频0"]


def test_history_persists_across_restart(client, stub_parse, temp_db):
    """记录落在磁盘上：换个新连接读（相当于后端重启）依然在。"""
    client.post("/api/parse", json={"url": "https://www.bilibili.com/video/BV1xx"})

    conn = sqlite3.connect(temp_db)
    try:
        rows = conn.execute("SELECT url, title, status FROM history").fetchall()
    finally:
        conn.close()
    assert rows == [("https://www.bilibili.com/video/BV1xx", "示例视频标题", "parsed")]

    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as restarted:
        body = restarted.get("/api/history").json()

    assert body["total"] == 1
    assert body["items"][0]["title"] == "示例视频标题"


def test_history_list_is_empty_without_records(client):
    """还没有解析过任何视频时，列表接口返回空列表（前端据此展示引导文案）。"""
    body = client.get("/api/history").json()

    assert body["total"] == 0
    assert body["items"] == []
