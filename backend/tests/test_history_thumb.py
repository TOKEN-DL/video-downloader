"""封面本地缓存的接口级测试。

唯一接缝是 HTTP API：打真实应用，验证「解析 → 后台缓存封面 → 本地封面接口取图」
这条链路；外部世界（yt-dlp 解析、封面下载）打桩。
"""
import os
import threading
import time

import config

from conftest import FAKE_IMAGE, FakeThumbResponse


def _thumb_file(record_id: int) -> str:
    """封面落盘位置（设计文档：backend/history/thumbs/{record_id}.jpg）。"""
    return os.path.join(config.HISTORY_THUMB_DIR, f"{record_id}.jpg")


def _wait_until(predicate, timeout: float = 5.0) -> bool:
    """等后台线程把封面缓存好（封面下载是异步的）。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def test_parse_caches_thumbnail_and_serves_it_locally(
    client, stub_parse, stub_thumb_download
):
    """解析成功后封面被缓存到本地，本地封面接口能取到图片。"""
    resp = client.post("/api/parse", json={"url": "https://www.bilibili.com/video/BV1xx"})
    assert resp.status_code == 200
    record_id = resp.json()["history_id"]

    # 封面在后台线程里下载，列表接口出现本地封面路径即缓存完成
    cached = _wait_until(
        lambda: client.get("/api/history").json()["items"][0].get("thumb_path")
    )
    assert cached, "解析后封面应被缓存到本地并在列表里返回 thumb_path"

    assert stub_thumb_download.requests, "封面应通过 httpx 下载"
    assert os.path.isfile(_thumb_file(record_id))

    thumb = client.get(f"/api/history/thumb/{record_id}")
    assert thumb.status_code == 200
    assert thumb.content == FAKE_IMAGE
    assert thumb.headers["content-type"].startswith("image/")


def test_thumbnail_endpoint_returns_404_when_not_cached(client):
    """没有本地封面文件时返回 404，前端据此回退远程封面。"""
    resp = client.get("/api/history/thumb/4242")

    assert resp.status_code == 404


def test_parse_survives_thumbnail_download_failure(
    client, stub_parse, stub_thumb_download
):
    """封面下载失败（防盗链 / 超时 / 404）不影响解析结果，只是没有本地封面。"""
    stub_thumb_download.error = RuntimeError("403 Forbidden")

    resp = client.post("/api/parse", json={"url": "https://www.bilibili.com/video/BV1xx"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "示例视频标题"
    assert body["history_id"] is not None

    record_id = body["history_id"]
    # 等后台线程把这次下载尝试做完
    assert _wait_until(lambda: stub_thumb_download.finished), "封面应尝试下载过"

    item = client.get("/api/history").json()["items"][0]
    assert item["thumb_path"] == ""
    assert client.get(f"/api/history/thumb/{record_id}").status_code == 404


def test_delete_record_removes_cached_thumbnail(
    client, stub_parse, stub_thumb_download
):
    """删除记录时，对应的本地封面文件一起删掉。"""
    resp = client.post("/api/parse", json={"url": "https://www.bilibili.com/video/BV1xx"})
    record_id = resp.json()["history_id"]
    assert _wait_until(
        lambda: client.get("/api/history").json()["items"][0].get("thumb_path")
    )
    assert os.path.isfile(_thumb_file(record_id))

    deleted = client.delete(f"/api/history/{record_id}")

    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True}
    assert not os.path.exists(_thumb_file(record_id))
    assert client.get("/api/history").json()["total"] == 0
    assert client.get(f"/api/history/thumb/{record_id}").status_code == 404


def test_clear_records_removes_all_cached_thumbnails(
    client, stub_parse, stub_thumb_download
):
    """清空全部记录时，所有本地封面文件一起删掉。"""
    record_ids = []
    for i in range(2):
        resp = client.post("/api/parse", json={"url": f"https://example.com/video/{i}"})
        record_ids.append(resp.json()["history_id"])

    assert _wait_until(
        lambda: all(
            item.get("thumb_path")
            for item in client.get("/api/history").json()["items"]
        )
    )
    for record_id in record_ids:
        assert os.path.isfile(_thumb_file(record_id))

    cleared = client.delete("/api/history")

    assert cleared.status_code == 200
    assert cleared.json() == {"deleted": 2}
    for record_id in record_ids:
        assert not os.path.exists(_thumb_file(record_id))
    assert client.get("/api/history").json()["total"] == 0


def test_thumbnail_download_does_not_block_parse_response(
    client, stub_parse, stub_thumb_download
):
    """封面下载在后台跑：解析响应不等封面下载完就返回。"""
    started = threading.Event()
    finished = threading.Event()
    release = threading.Event()

    def slow_get(url, headers=None):
        started.set()
        try:
            release.wait(10)  # 卡住封面下载
            return FakeThumbResponse(content=FAKE_IMAGE)
        finally:
            finished.set()

    stub_thumb_download.get = slow_get

    try:
        resp = client.post("/api/parse", json={"url": "https://www.bilibili.com/video/BV1xx"})

        assert resp.status_code == 200
        assert started.is_set(), "封面应在后台线程下载"
        assert not finished.is_set(), "解析响应不该等封面下载完成"
    finally:
        release.set()
