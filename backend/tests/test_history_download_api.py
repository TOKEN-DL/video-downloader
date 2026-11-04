"""历史记录重新下载的接口测试。

唯一接缝是 HTTP API：打真实应用、真实 SQLite，
只把「外部世界」（yt-dlp / 抖音解析、下载任务启动）打桩。
"""
import pytest


@pytest.fixture(autouse=True)
def clean_parse_cache():
    """解析缓存是进程内的，测试之间清干净，避免互相污染。"""
    from services import video_service

    video_service._parse_cache.clear()
    yield
    video_service._parse_cache.clear()


@pytest.fixture
def stub_download_start(monkeypatch):
    """打桩下载任务启动：记录启动参数并返回假 task_id，避免真下载大文件。"""
    from services import video_service

    started = []

    def fake_start_download(url, format_id):
        started.append({"mode": "yt-dlp", "url": url, "format_id": format_id})
        return "task_ytdlp"

    def fake_start_fallback_download(video_url):
        started.append({"mode": "direct", "url": video_url})
        return "task_direct"

    monkeypatch.setattr(video_service, "start_download", fake_start_download)
    monkeypatch.setattr(video_service, "start_fallback_download", fake_start_fallback_download)
    return started


def _create_record(client, url="https://www.bilibili.com/video/BV1xx"):
    """用解析接口建一条历史记录，返回记录 id。"""
    resp = client.post("/api/parse", json={"url": url})
    assert resp.status_code == 200
    return resp.json()["history_id"]


def test_history_download_starts_ytdlp_download(client, stub_parse, stub_thumb_download,
                                                stub_download_start):
    """历史记录里选一档清晰度下载：返回任务标识，并按该清晰度启动 yt-dlp 下载。"""
    stub_parse.result = {
        **stub_parse.result,
        "formats": [
            {"format_id": "401", "resolution": "1080p", "ext": "mp4", "filesize": 100},
            {"format_id": "30016", "resolution": "720p", "ext": "mp4", "filesize": 50},
        ],
    }
    record_id = _create_record(client)

    resp = client.post(f"/api/history/{record_id}/download", json={"format_id": "30016"})

    assert resp.status_code == 200
    assert resp.json()["task_id"] == "task_ytdlp"
    assert stub_download_start == [
        {
            "mode": "yt-dlp",
            "url": "https://www.bilibili.com/video/BV1xx",
            "format_id": "30016",
        }
    ]


def test_history_download_defaults_to_highest_resolution(client, stub_parse, stub_thumb_download,
                                                         stub_download_start):
    """不指定清晰度时，默认选记录里分辨率最高的一档（不是列表里的第一项）。"""
    stub_parse.result = {
        **stub_parse.result,
        "formats": [
            {"format_id": "30016", "resolution": "720p", "ext": "mp4", "filesize": 50},
            {"format_id": "401", "resolution": "1080p", "ext": "mp4", "filesize": 100},
        ],
    }
    record_id = _create_record(client)

    resp = client.post(f"/api/history/{record_id}/download", json={})

    assert resp.status_code == 200
    assert resp.json()["task_id"] == "task_ytdlp"
    assert stub_download_start == [
        {
            "mode": "yt-dlp",
            "url": "https://www.bilibili.com/video/BV1xx",
            "format_id": "401",
        }
    ]


def test_history_download_uses_direct_url_for_douyin(client, stub_parse, stub_thumb_download,
                                                     stub_download_start):
    """抖音这类自带直链的解析结果：走直链下载，不走 yt-dlp。"""
    stub_parse.result = {
        **stub_parse.result,
        "platform": "douyin",
        "formats": [
            {"format_id": "fallback_best", "resolution": "best", "ext": "mp4", "filesize": None},
        ],
        "_fallback": True,
        "_video_url": "https://cdn.example.com/douyin-signed.mp4",
    }
    record_id = _create_record(client, url="https://www.douyin.com/video/123")

    resp = client.post(f"/api/history/{record_id}/download", json={})

    assert resp.status_code == 200
    assert resp.json()["task_id"] == "task_direct"
    assert stub_download_start == [
        {"mode": "direct", "url": "https://cdn.example.com/douyin-signed.mp4"}
    ]


def test_history_download_unknown_record_returns_404(client, stub_download_start):
    """记录不存在时返回 404「记录不存在」，并且不会启动任何下载。"""
    resp = client.post("/api/history/9999/download", json={})

    assert resp.status_code == 404
    assert resp.json()["detail"] == "记录不存在"
    assert stub_download_start == []


def test_history_download_invalid_source_keeps_record(client, stub_parse, stub_thumb_download,
                                                      stub_download_start, monkeypatch):
    """视频源已失效：给出明确的失败提示，并且不动这条历史记录。"""
    record_id = _create_record(client)

    # 源失效：重新解析直接报错（视频下架 / 链接过期）
    from services import video_service

    def boom(url):
        raise RuntimeError("Video unavailable")

    monkeypatch.setattr(video_service, "parse_video", boom)

    resp = client.post(f"/api/history/{record_id}/download", json={})

    assert resp.status_code == 400
    assert "视频源已失效" in resp.json()["detail"]
    assert stub_download_start == []

    # 记录本身完好：还能查详情，用户可以自己删
    detail = client.get(f"/api/history/{record_id}")
    assert detail.status_code == 200
    assert detail.json()["url"] == "https://www.bilibili.com/video/BV1xx"


def test_home_download_recovers_douyin_after_restart(client, stub_parse, stub_thumb_download,
                                                     stub_download_start):
    """服务重启（进程内解析缓存清空）后，首页下载仍能重新解析拿到抖音直链。"""
    from services import video_service

    stub_parse.result = {
        **stub_parse.result,
        "platform": "douyin",
        "formats": [
            {"format_id": "fallback_best", "resolution": "best", "ext": "mp4", "filesize": None},
        ],
        "_fallback": True,
        "_video_url": "https://cdn.example.com/fresh-signed.mp4",
    }
    # 模拟服务重启：进程内的解析缓存没了
    video_service._parse_cache.clear()

    resp = client.post("/api/download", json={
        "url": "https://www.douyin.com/video/123",
        "format_id": "fallback_best",
    })

    assert resp.status_code == 200
    assert resp.json()["task_id"] == "task_direct"
    assert stub_download_start == [
        {"mode": "direct", "url": "https://cdn.example.com/fresh-signed.mp4"}
    ]


def test_history_download_recovers_douyin_after_restart(client, stub_parse, stub_thumb_download,
                                                       stub_download_start):
    """服务重启后，从历史记录下载抖音视频仍能成功：重新解析拿到新的签名直链。"""
    from services import video_service

    stub_parse.result = {
        **stub_parse.result,
        "platform": "douyin",
        "formats": [
            {"format_id": "fallback_best", "resolution": "best", "ext": "mp4", "filesize": None},
        ],
        "_fallback": True,
        "_video_url": "https://cdn.example.com/old-signed.mp4",
    }
    record_id = _create_record(client, url="https://www.douyin.com/video/123")

    # 模拟服务重启：进程内的解析缓存没了，签名直链也换了新的
    video_service._parse_cache.clear()
    stub_parse.result = {
        **stub_parse.result,
        "_video_url": "https://cdn.example.com/new-signed.mp4",
    }

    resp = client.post(f"/api/history/{record_id}/download", json={})

    assert resp.status_code == 200
    assert resp.json()["task_id"] == "task_direct"
    assert stub_download_start == [
        {"mode": "direct", "url": "https://cdn.example.com/new-signed.mp4"}
    ]


def test_home_download_still_starts_ytdlp_download(client, stub_parse, stub_thumb_download,
                                                    stub_download_start):
    """首页下载的既有行为不变：普通视频仍走 yt-dlp，返回任务标识。"""
    resp = client.post("/api/download", json={
        "url": "https://www.bilibili.com/video/BV1xx",
        "format_id": "30016",
    })

    assert resp.status_code == 200
    assert resp.json()["task_id"] == "task_ytdlp"
    assert stub_download_start == [
        {
            "mode": "yt-dlp",
            "url": "https://www.bilibili.com/video/BV1xx",
            "format_id": "30016",
        }
    ]
