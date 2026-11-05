"""历史记录列表 / 详情字段的接口级测试。

唯一接缝是 HTTP API：打真实应用、真实 SQLite，只把外部世界
（视频解析、字幕提取、AI 模型）打桩。

这里守的是几条「字段边界」：
- 列表项要带 AI 失败原因（列表页 hover 徽标靠它区分「没字幕」和「模型报错」）
- 列表项不能带字幕 / AI 大字段（分页接口要保持轻量）
- 详情要给出默认清晰度（前端不再自己实现一遍挑选逻辑）
"""
import time

VIDEO_URL = "https://www.bilibili.com/video/BV1xx"

# 列表接口刻意不返回的大字段：分页接口要保持轻量
HEAVY_FIELDS = ("subtitle_data", "transcript", "ai_result", "mindmap_markdown")


def _wait_task(client, task_id, timeout=15.0):
    """等 AI 任务跑到终态，返回状态接口的响应体。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/ai/summarize/status/{task_id}").json()
        if body["status"] in ("done", "error"):
            return body
        time.sleep(0.05)
    raise AssertionError(f"AI 任务未在 {timeout} 秒内结束")


def _fail_ai(client, stub_parse, stub_ai, stub_subtitle, url=VIDEO_URL):
    """把一条记录跑到「AI 失败」，返回记录 id。"""
    parsed = client.post("/api/parse", json={"url": url}).json()
    record_id = parsed["history_id"]

    task = client.post(
        "/api/ai/summarize", json={"url": url, "history_id": record_id}
    ).json()
    assert _wait_task(client, task["task_id"])["status"] == "error"
    return record_id


def test_history_list_item_exposes_ai_failure_reason(
    client, stub_parse, stub_ai, stub_subtitle
):
    """AI 失败时列表项带上失败原因：列表页 hover 徽标要靠它说明为什么失败。"""
    stub_subtitle.data = None
    _fail_ai(client, stub_parse, stub_ai, stub_subtitle)

    body = client.get("/api/history").json()

    assert body["total"] == 1
    item = body["items"][0]
    assert item["status"] == "ai_failed"
    assert item["error"] == "该视频没有字幕，暂不支持 AI 总结"


def test_history_list_item_error_is_empty_when_ai_succeeded(
    client, stub_parse, stub_ai, stub_subtitle
):
    """AI 成功时列表项的 error 为空，不残留上一次的失败原因。"""
    parsed = client.post("/api/parse", json={"url": VIDEO_URL}).json()
    task = client.post(
        "/api/ai/summarize",
        json={"url": VIDEO_URL, "history_id": parsed["history_id"]},
    ).json()
    assert _wait_task(client, task["task_id"])["status"] == "done"

    item = client.get("/api/history").json()["items"][0]

    assert item["status"] == "ai_done"
    assert not item["error"]


def test_history_list_item_omits_heavy_fields(client, stub_parse, stub_ai, stub_subtitle):
    """列表接口不返回字幕 / AI 大字段：分页接口要保持轻量。"""
    parsed = client.post("/api/parse", json={"url": VIDEO_URL}).json()
    task = client.post(
        "/api/ai/summarize",
        json={"url": VIDEO_URL, "history_id": parsed["history_id"]},
    ).json()
    assert _wait_task(client, task["task_id"])["status"] == "done"

    item = client.get("/api/history").json()["items"][0]

    for field in HEAVY_FIELDS:
        assert field not in item, f"列表项不应包含 {field}"

    # 详情接口确实有这些字段：说明上面排除的是列表接口的取舍，不是数据本身缺失
    detail = client.get(f"/api/history/{parsed['history_id']}").json()
    for field in HEAVY_FIELDS:
        assert field in detail


def test_history_detail_exposes_default_format_id(client, stub_parse):
    """详情给出默认清晰度：该记录可用格式中分辨率最高的一档。"""
    stub_parse.result = {
        **stub_parse.result,
        "formats": [
            {"format_id": "30016", "resolution": "720p", "ext": "mp4", "filesize": 50},
            {"format_id": "401", "resolution": "1080p", "ext": "mp4", "filesize": 100},
            {"format_id": "18", "resolution": "360p", "ext": "mp4", "filesize": 20},
        ],
    }
    parsed = client.post("/api/parse", json={"url": VIDEO_URL}).json()

    detail = client.get(f"/api/history/{parsed['history_id']}").json()

    assert detail["default_format_id"] == "401"


def test_history_detail_default_format_id_falls_back_to_first_undisparable_format(
    client, stub_parse
):
    """分辨率没法比较时（如抖音的 'best'）：默认清晰度取第一档可用格式。"""
    stub_parse.result = {
        **stub_parse.result,
        "formats": [
            {"format_id": "fallback_best", "resolution": "best", "ext": "mp4", "filesize": None},
        ],
    }
    parsed = client.post("/api/parse", json={"url": VIDEO_URL}).json()

    detail = client.get(f"/api/history/{parsed['history_id']}").json()

    assert detail["default_format_id"] == "fallback_best"


def test_history_detail_default_format_id_is_empty_without_formats(client, stub_parse):
    """记录里没有可用格式时，默认清晰度为空字符串（前端据此禁用下载按钮）。"""
    stub_parse.result = {**stub_parse.result, "formats": []}
    parsed = client.post("/api/parse", json={"url": VIDEO_URL}).json()

    detail = client.get(f"/api/history/{parsed['history_id']}").json()

    assert detail["default_format_id"] == ""
