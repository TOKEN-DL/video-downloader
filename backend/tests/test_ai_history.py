"""AI 分析结果回写历史记录的接口级测试。

唯一接缝是 HTTP API：打真实应用、真实 SQLite，只把外部世界
（视频解析、字幕提取、AI 模型）打桩。断言看 HTTP 响应与库里的行，
不碰私有函数。
"""
import time

from conftest import FAKE_AI_RESULT, FAKE_MINDMAP, FAKE_SUBTITLE

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


def test_ai_result_is_written_back_to_its_history_record(
    client, stub_parse, stub_ai, stub_subtitle
):
    """AI 总结跑完后，结果、字幕、思维导图写回同一条历史记录，状态变为「AI 已总结」。"""
    parsed = client.post("/api/parse", json={"url": VIDEO_URL}).json()
    record_id = parsed["history_id"]

    task = client.post(
        "/api/ai/summarize", json={"url": VIDEO_URL, "history_id": record_id}
    ).json()
    status = _wait_task(client, task["task_id"])
    assert status["status"] == "done"

    detail = client.get(f"/api/history/{record_id}").json()
    assert detail["status"] == "ai_done"
    assert detail["has_ai"] is True
    assert detail["ai_result"]["summary"] == FAKE_AI_RESULT["summary"]
    assert detail["ai_result"]["highlights"][0]["timestamp"] == "01:23"
    assert detail["ai_result"]["highlights"][0]["point"] == "先讲问题再给方案"
    assert detail["ai_result"]["terms"][0]["term"] == "缓存穿透"
    assert detail["ai_result"]["terms"][0]["explanation"] == "请求绕过缓存直接打到数据库"
    assert detail["ai_result"]["qa"][0]["question"] == "视频的核心结论是什么？"
    assert detail["ai_result"]["qa"][0]["answer"] == "缓存要分层设计。"
    assert detail["subtitle_data"] == FAKE_SUBTITLE
    assert detail["transcript"] == "开场白\n第二句话"
    assert detail["mindmap_markdown"] == FAKE_MINDMAP


def test_video_without_subtitles_is_marked_ai_failed_but_kept(
    client, stub_parse, stub_ai, stub_subtitle
):
    """视频没有字幕时 AI 跑不通：记录依然保留，状态变为「AI 失败」并带上原因。"""
    stub_subtitle.data = None
    parsed = client.post("/api/parse", json={"url": VIDEO_URL}).json()
    record_id = parsed["history_id"]

    task = client.post(
        "/api/ai/summarize", json={"url": VIDEO_URL, "history_id": record_id}
    ).json()
    status = _wait_task(client, task["task_id"])
    assert status["status"] == "error"

    detail = client.get(f"/api/history/{record_id}").json()
    assert detail["status"] == "ai_failed"
    assert detail["error"] == "该视频没有字幕，暂不支持 AI 总结"
    # 视频本身的信息一条都不能少
    assert detail["title"] == "示例视频标题"
    assert detail["url"] == VIDEO_URL
    assert detail["formats"]


def test_ai_model_error_is_marked_ai_failed_but_kept(
    client, stub_parse, stub_ai, stub_subtitle
):
    """模型报错时记录同样保留，状态变为「AI 失败」，失败原因写得进去。"""
    stub_ai.error = RuntimeError("模型连接超时")
    parsed = client.post("/api/parse", json={"url": VIDEO_URL}).json()
    record_id = parsed["history_id"]

    task = client.post(
        "/api/ai/summarize", json={"url": VIDEO_URL, "history_id": record_id}
    ).json()
    status = _wait_task(client, task["task_id"])
    assert status["status"] == "error"

    detail = client.get(f"/api/history/{record_id}").json()
    assert detail["status"] == "ai_failed"
    assert "模型连接超时" in detail["error"]
    assert detail["title"] == "示例视频标题"


def test_ai_result_falls_back_to_the_record_matched_by_url(
    client, stub_parse, stub_ai, stub_subtitle
):
    """请求没带 history_id 时，后端按 url 兜底匹配最近一条记录并回写。"""
    parsed = client.post("/api/parse", json={"url": VIDEO_URL}).json()
    record_id = parsed["history_id"]

    task = client.post("/api/ai/summarize", json={"url": VIDEO_URL}).json()
    status = _wait_task(client, task["task_id"])
    assert status["status"] == "done"

    detail = client.get(f"/api/history/{record_id}").json()
    assert detail["status"] == "ai_done"
    assert detail["ai_result"]["summary"] == FAKE_AI_RESULT["summary"]


def test_ai_result_for_unparsed_url_still_finishes_without_touching_history(
    client, stub_parse, stub_ai, stub_subtitle
):
    """没有对应历史记录时，AI 任务照常跑完，只是不往库里写。"""
    task = client.post(
        "/api/ai/summarize", json={"url": "https://example.com/video/never-parsed"}
    ).json()

    status = _wait_task(client, task["task_id"])
    assert status["status"] == "done"
    assert client.get("/api/history").json()["total"] == 0


def test_failed_ai_run_keeps_the_previous_ai_result(
    client, stub_parse, stub_ai, stub_subtitle
):
    """重新跑 AI 失败时，之前跑出来的结果不清空：同一个视频，旧数据依然成立。"""
    parsed = client.post("/api/parse", json={"url": VIDEO_URL}).json()
    record_id = parsed["history_id"]

    task = client.post(
        "/api/ai/summarize", json={"url": VIDEO_URL, "history_id": record_id}
    ).json()
    assert _wait_task(client, task["task_id"])["status"] == "done"

    stub_ai.error = RuntimeError("模型连接超时")
    second = client.post(
        "/api/ai/summarize", json={"url": VIDEO_URL, "history_id": record_id}
    ).json()
    assert _wait_task(client, second["task_id"])["status"] == "error"

    detail = client.get(f"/api/history/{record_id}").json()
    assert detail["status"] == "ai_failed"
    assert detail["ai_result"]["summary"] == FAKE_AI_RESULT["summary"]
    assert detail["mindmap_markdown"] == FAKE_MINDMAP


def _record_with_ai(client, stub_parse, stub_ai, stub_subtitle):
    """跑一遍完整链路，返回一条已写入 AI 结果的记录 ID。"""
    parsed = client.post("/api/parse", json={"url": VIDEO_URL}).json()
    record_id = parsed["history_id"]
    task = client.post(
        "/api/ai/summarize", json={"url": VIDEO_URL, "history_id": record_id}
    ).json()
    assert _wait_task(client, task["task_id"])["status"] == "done"
    return record_id


def test_history_record_can_be_exported_as_markdown(
    client, stub_parse, stub_ai, stub_subtitle
):
    """记录可以导出 Markdown：正文含标题与四段结构化内容。"""
    record_id = _record_with_ai(client, stub_parse, stub_ai, stub_subtitle)

    resp = client.get(f"/api/history/{record_id}/export", params={"format": "markdown"})

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/markdown")
    body = resp.text
    assert body.startswith("# 示例视频标题")
    assert "视频讲了一个关于缓存设计的例子。" in body
    assert "[01:23] 先讲问题再给方案" in body
    assert "缓存穿透" in body
    assert "缓存要分层设计。" in body
    # 中文文件名按 RFC 5987 编码，响应头保持纯 ASCII
    disposition = resp.headers["content-disposition"]
    assert disposition.startswith("attachment; filename*=UTF-8''")


def test_history_record_can_be_exported_as_pdf(
    client, stub_parse, stub_ai, stub_subtitle
):
    """记录可以导出 PDF：返回真正的 PDF 字节流。"""
    record_id = _record_with_ai(client, stub_parse, stub_ai, stub_subtitle)

    resp = client.get(f"/api/history/{record_id}/export", params={"format": "pdf"})

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")


def test_export_of_missing_record_reports_not_found(client):
    """导出不存在的记录返回 404。"""
    resp = client.get("/api/history/9999/export")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "记录不存在"


def test_export_without_ai_result_is_rejected(client, stub_parse):
    """还没跑过 AI 的记录没有可导出的总结，给出明确提示而不是空文件。"""
    parsed = client.post("/api/parse", json={"url": VIDEO_URL}).json()

    resp = client.get(f"/api/history/{parsed['history_id']}/export")

    assert resp.status_code == 400
    assert "AI" in resp.json()["detail"]
