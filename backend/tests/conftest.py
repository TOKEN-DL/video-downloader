"""pytest 公共夹具。

测试只走 HTTP API 这一条接缝，用真实的 FastAPI 应用打真实的 SQLite，
只把「外部世界」（yt-dlp 解析、字幕提取、AI 总结、下载任务）打桩。

数据库路径在运行时指向临时目录，绝不触碰真实的 backend/history.db。
"""
import os
import sys

import pytest

# 让测试能 import config / database / services（与 uvicorn 的运行方式一致）
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import config  # noqa: E402
from database import db  # noqa: E402


DEFAULT_VIDEO_INFO = {
    "title": "示例视频标题",
    "thumbnail": "https://example.com/cover.jpg",
    "duration": 754.0,
    "author": "示例作者",
    "platform": "bilibili",
    "formats": [
        {"format_id": "30016", "resolution": "720p", "ext": "mp4", "filesize": 12345678},
    ],
    "subtitles": [],
}


class ParseStub:
    """打桩视频解析（yt-dlp 属于外部世界，不该在测试里真联网）。"""

    def __init__(self):
        self.result = dict(DEFAULT_VIDEO_INFO)
        self.calls = []

    def __call__(self, url: str) -> dict:
        self.calls.append(url)
        return self.result


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """把 config.DB_PATH / config.HISTORY_THUMB_DIR 指向临时目录，并重置线程内的连接缓存。"""
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "history.db"))
    monkeypatch.setattr(config, "HISTORY_THUMB_DIR", str(tmp_path / "thumbs"))
    db.close_conn()
    yield config.DB_PATH
    db.close_conn()


@pytest.fixture
def client(temp_db):
    """指向临时库的真实应用客户端。"""
    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def stub_parse(monkeypatch):
    """替换掉 yt-dlp 解析；路由层照常编排，其余逻辑真实执行。"""
    from api import router

    stub = ParseStub()
    monkeypatch.setattr(router.video_service, "parse_video", stub)
    return stub
