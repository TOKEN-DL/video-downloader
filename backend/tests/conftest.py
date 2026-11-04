"""pytest 公共夹具。

测试只走 HTTP API 这一条接缝，用真实的 FastAPI 应用打真实的 SQLite，
只把「外部世界」（yt-dlp 解析、字幕提取、AI 总结、封面下载、下载任务）打桩。

数据库路径与封面缓存目录在运行时指向临时目录，绝不触碰真实的
backend/history.db 和 backend/history/thumbs。
"""
import os
import sys
import time
from types import SimpleNamespace

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

# 外部世界（字幕提取 / AI 模型）的替身数据：固定字面量，测试断言以此为准。
FAKE_SUBTITLE = [
    {"time": "0:00", "text": "开场白"},
    {"time": "0:12", "text": "第二句话"},
]

FAKE_AI_RESULT = {
    "summary": "视频讲了一个关于缓存设计的例子。",
    "highlights": [{"timestamp": "01:23", "point": "先讲问题再给方案"}],
    "terms": [{"term": "缓存穿透", "explanation": "请求绕过缓存直接打到数据库"}],
    "qa": [{"question": "视频的核心结论是什么？", "answer": "缓存要分层设计。"}],
}

FAKE_MINDMAP = "# 示例视频标题\n\n## 第一节\n- 缓存分层\n"


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
def temp_thumbs(tmp_path, monkeypatch):
    """把封面缓存目录指向临时目录，绝不碰真实的 backend/history/thumbs。"""
    thumb_dir = tmp_path / "thumbs"
    monkeypatch.setattr(config, "HISTORY_THUMB_DIR", str(thumb_dir))
    return thumb_dir


@pytest.fixture
def client(temp_db, temp_thumbs):
    """指向临时库 / 临时封面目录的真实应用客户端。"""
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


# ============ 封面下载打桩 ============

FAKE_IMAGE = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"fake-jpeg-bytes"


class FakeThumbResponse:
    """httpx.Response 的最小替身。"""

    def __init__(self, content: bytes = b"", status_code: int = 200,
                 content_type: str = "image/jpeg"):
        self.content = content
        self.status_code = status_code
        self.headers = {"content-type": content_type}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeThumbClient:
    """打桩封面下载（httpx 属于外部世界，测试里不该真联网）。"""

    def __init__(self, content: bytes = FAKE_IMAGE):
        self.content = content
        self.requests: list[dict] = []
        self.finished = False
        self.error: Exception | None = None  # 赋异常即模拟防盗链 / 超时 / 404

    def __call__(self, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url, headers=None):
        self.requests.append({"url": url, "headers": dict(headers or {})})
        try:
            if self.error is not None:
                raise self.error
            return FakeThumbResponse(content=self.content)
        finally:
            self.finished = True


@pytest.fixture
def stub_thumb_download(monkeypatch):
    """替换封面下载用的 httpx.Client（只影响 thumb_service，不动全局 httpx）。"""
    from services import thumb_service

    stub = FakeThumbClient()
    monkeypatch.setattr(thumb_service, "httpx", SimpleNamespace(Client=stub))
    yield stub
    # 后台线程可能还在下载：等它这次请求结束，避免补丁撤销后线程去真联网
    if stub.requests:
        deadline = time.time() + 5
        while not stub.finished and time.time() < deadline:
            time.sleep(0.05)


# ============ AI 总结 / 字幕提取打桩 ============


class AiStub:
    """打桩 AI 总结与思维导图生成（模型调用属于外部世界，不该在测试里真联网）。"""

    def __init__(self):
        self.result = dict(FAKE_AI_RESULT)
        self.mindmap = FAKE_MINDMAP
        self.error: Exception | None = None  # 赋异常即模拟模型报错
        self.transcript = None
        self.title = None

    def summarize(self, transcript: str, title: str) -> dict:
        if self.error is not None:
            raise self.error
        self.transcript = transcript
        self.title = title
        return self.result

    def generate_mindmap_markdown(self, summary: dict, title: str) -> str:
        if self.error is not None:
            raise self.error
        return self.mindmap


@pytest.fixture
def stub_ai(monkeypatch):
    """替换 AI 总结与思维导图生成；其余链路（路由编排、落库）真实执行。"""
    from services import ai_service

    stub = AiStub()
    monkeypatch.setattr(ai_service, "summarize", stub.summarize)
    monkeypatch.setattr(ai_service, "generate_mindmap_markdown", stub.generate_mindmap_markdown)
    return stub


class SubtitleStub:
    """打桩字幕提取（yt-dlp / 平台接口属于外部世界）。"""

    def __init__(self):
        self.data = list(FAKE_SUBTITLE)
        self.calls = []

    def __call__(self, url: str, lang: str | None = None):
        self.calls.append((url, lang))
        return self.data


@pytest.fixture
def stub_subtitle(monkeypatch):
    """替换字幕提取；data 置 None 即模拟「该视频没有字幕」。"""
    from services import subtitle_service

    stub = SubtitleStub()
    monkeypatch.setattr(subtitle_service, "get_subtitle_data", stub)
    return stub
