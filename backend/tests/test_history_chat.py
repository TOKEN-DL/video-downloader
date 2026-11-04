"""历史详情页基于已存字幕继续 AI 问答的接口级测试。

唯一接缝是 HTTP API：打真实应用、真实 SQLite，只把外部世界
（视频解析、字幕提取、AI 模型）打桩。断言看 HTTP 响应与库里的行，
不碰私有函数。
"""
import time

from conftest import FAKE_CHAT_REPLY, FAKE_SUBTITLE

VIDEO_URL = "https://www.bilibili.com/video/BV1xx"


def _wait_task(client, task_id, timeout=15.0):
    """等 AI 任务跑到终态，返回状态接口的响应体。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/ai/summarize/status/{task_id}").json()
        if body["status"] in ("done", "error"):
            return body
        time.sleep(0.05)
    raise AssertionError(f"AI 任务未在 {timeout} 秒内结束")


def _record_with_ai(client, stub_parse, stub_ai, stub_subtitle):
    """跑一遍完整链路，返回一条已写入 AI 结果的记录 ID。"""
    parsed = client.post("/api/parse", json={"url": VIDEO_URL}).json()
    record_id = parsed["history_id"]
    task = client.post(
        "/api/ai/summarize", json={"url": VIDEO_URL, "history_id": record_id}
    ).json()
    assert _wait_task(client, task["task_id"])["status"] == "done"
    return record_id


def test_history_detail_returns_the_stored_transcript(
    client, stub_parse, stub_ai, stub_subtitle, stub_thumb_download
):
    """详情接口把当初存下的字幕全文交回来 —— 后续 AI 问答的上下文就来自这里。"""
    record_id = _record_with_ai(client, stub_parse, stub_ai, stub_subtitle)

    detail = client.get(f"/api/history/{record_id}").json()

    assert detail["transcript"] == "开场白\n第二句话"
    assert detail["subtitle_data"] == FAKE_SUBTITLE


def test_chat_uses_the_transcript_stored_in_the_record(
    client, stub_parse, stub_ai, stub_subtitle, stub_thumb_download, stub_ai_chat
):
    """用记录里存下的字幕发起对话：能正常回答，上下文就是那份字幕。"""
    record_id = _record_with_ai(client, stub_parse, stub_ai, stub_subtitle)
    detail = client.get(f"/api/history/{record_id}").json()

    resp = client.post(
        "/api/ai/chat",
        json={
            "url": "",
            "messages": [{"role": "user", "content": "这个视频的核心观点是什么？"}],
            "transcript_context": detail["transcript"],
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["message"]["role"] == "assistant"
    assert body["message"]["content"] == FAKE_CHAT_REPLY
    # 上下文用的就是库里存下的那份字幕
    assert stub_ai_chat.calls[0]["transcript"] == detail["transcript"]
    assert stub_ai_chat.calls[0]["messages"][-1]["content"] == "这个视频的核心观点是什么？"


def test_chat_neither_reparses_the_video_nor_reruns_the_analysis(
    client, stub_parse, stub_ai, stub_subtitle, stub_thumb_download, stub_ai_chat
):
    """提问不重新解析视频，也不重新跑一遍 AI 总结：直接用库里存下的数据。"""
    record_id = _record_with_ai(client, stub_parse, stub_ai, stub_subtitle)
    detail_before = client.get(f"/api/history/{record_id}").json()
    parse_calls_before = len(stub_parse.calls)
    summarize_calls_before = stub_ai.summarize_calls
    mindmap_calls_before = stub_ai.mindmap_calls

    resp = client.post(
        "/api/ai/chat",
        json={
            "url": "",
            "messages": [{"role": "user", "content": "这个视频的核心观点是什么？"}],
            "transcript_context": detail_before["transcript"],
        },
    )

    assert resp.status_code == 200
    # 没有重新解析视频
    assert len(stub_parse.calls) == parse_calls_before
    # 没有重新跑 AI 总结 / 思维导图
    assert stub_ai.summarize_calls == summarize_calls_before
    assert stub_ai.mindmap_calls == mindmap_calls_before
    # 记录里的分析结果原样保留，没有被改写
    detail_after = client.get(f"/api/history/{record_id}").json()
    assert detail_after["ai_result"] == detail_before["ai_result"]
    assert detail_after["mindmap_markdown"] == detail_before["mindmap_markdown"]
    assert detail_after["updated_at"] == detail_before["updated_at"]
    # 对话不落库：整条记录没多没少，刷新页面后对话清空、字幕与总结仍在
    assert detail_after == detail_before
    assert client.get("/api/history").json()["total"] == 1


def test_chat_without_transcript_context_is_rejected_before_calling_the_model(
    client, stub_ai_chat
):
    """没有字幕上下文（记录没字幕 / 还没跑过 AI）时给出明确提示，不发空上下文的请求。"""
    resp = client.post(
        "/api/ai/chat",
        json={
            "url": "",
            "messages": [{"role": "user", "content": "这个视频讲了什么？"}],
            "transcript_context": "",
        },
    )

    assert resp.status_code == 400
    assert "字幕" in resp.json()["detail"]
    # 模型根本没被叫起来：不存在「拿空上下文去问一句」
    assert stub_ai_chat.calls == []


def test_chat_with_blank_transcript_context_is_rejected_before_calling_the_model(
    client, stub_ai_chat
):
    """只有空白的字幕上下文同样拒绝：空上下文不能发给模型。"""
    resp = client.post(
        "/api/ai/chat",
        json={
            "url": "",
            "messages": [{"role": "user", "content": "这个视频讲了什么？"}],
            "transcript_context": "   \n\t  ",
        },
    )

    assert resp.status_code == 400
    assert "字幕" in resp.json()["detail"]
    assert stub_ai_chat.calls == []


def test_chat_does_not_require_a_video_url(client, stub_ai_chat):
    """历史记录没有可靠的链接上下文（可能是短链），对话不依赖 url。"""
    resp = client.post(
        "/api/ai/chat",
        json={
            "messages": [{"role": "user", "content": "这个视频的核心观点是什么？"}],
            "transcript_context": "开场白\n第二句话",
        },
    )

    assert resp.status_code == 200
    assert resp.json()["message"]["content"] == FAKE_CHAT_REPLY


def test_chat_model_failure_is_reported_to_the_caller(client, stub_ai_chat):
    """模型报错时把原因回传给调用方，不是静默失败。"""
    stub_ai_chat.error = RuntimeError("模型连接超时")

    resp = client.post(
        "/api/ai/chat",
        json={
            "url": "",
            "messages": [{"role": "user", "content": "这个视频讲了什么？"}],
            "transcript_context": "开场白\n第二句话",
        },
    )

    assert resp.status_code == 500
    assert "模型连接超时" in resp.json()["detail"]


def test_chat_with_blank_question_is_rejected_before_calling_the_model(client, stub_ai_chat):
    """空白的问题等于没问：不该发给模型。"""
    resp = client.post(
        "/api/ai/chat",
        json={
            "url": "",
            "messages": [{"role": "user", "content": "   "}],
            "transcript_context": "开场白\n第二句话",
        },
    )

    assert resp.status_code == 400
    assert stub_ai_chat.calls == []
