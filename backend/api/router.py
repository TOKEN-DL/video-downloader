import asyncio
import io
import uuid
import threading
import logging
import re
from urllib.parse import quote
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
import config
from services import video_service
from services import subtitle_service
from services import history_service
from services import ai_service
import httpx

logger = logging.getLogger("ai_router")

ai_task_progress: dict = {}

router = APIRouter()

# Cache parsed video info for fallback downloads
_parsed_cache: dict = {}


class ParseRequest(BaseModel):
    url: str


class DownloadRequest(BaseModel):
    url: str
    format_id: str


class SummarizeRequest(BaseModel):
    url: str
    subtitle_lang: str | None = None


class ChatRequest(BaseModel):
    url: str
    messages: list[dict]
    transcript_context: str


@router.post("/api/parse")
async def api_parse(req: ParseRequest):
    if not req.url.strip():
        raise HTTPException(status_code=400, detail="URL不能为空")
    try:
        url = req.url.strip()
        result = await asyncio.to_thread(video_service.parse_video, url)
        if result.get("_fallback"):
            _parsed_cache[url] = result
        # 解析成功即入库。落库失败（磁盘满等）只记日志，不阻断主流程：
        # 历史记录是辅助能力，解析结果照常返回（仅少一个 history_id）。
        try:
            history_id = history_service.upsert_parsed(url, result)
        except Exception as e:
            logger.error(f"历史记录落库失败（{url}）: {type(e).__name__}: {e}")
            history_id = None
        if history_id is not None:
            result = {**result, "history_id": history_id}
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"解析失败: {str(e)}")


@router.get("/api/history")
async def api_history_list(
    page: int = 1,
    page_size: int | None = None,
    platform: str | None = None,
    keyword: str | None = None,
):
    """历史记录分页列表。items 不含字幕 / AI 大字段，保证接口轻量。"""
    return history_service.list_records(
        page=page,
        page_size=page_size,
        platform=platform,
        keyword=keyword,
    )


@router.get("/api/history/{record_id}")
async def api_history_detail(record_id: int):
    """记录详情：含格式列表与字幕 / AI 数据。

    路由声明在 /api/history 之后、/api/history/thumb/{id} 之前不会冲突：
    {record_id} 是 int，匹配不到非数字路径。
    """
    record = history_service.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    return record


@router.delete("/api/history/{record_id}")
async def api_history_delete(record_id: int):
    """删除单条记录（连同它缓存的本地封面文件）。"""
    if not history_service.delete_record(record_id):
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"deleted": True}


@router.delete("/api/history")
async def api_history_clear():
    """清空全部历史记录（连同它们缓存的本地封面文件）。"""
    return {"deleted": history_service.clear_records()}


@router.post("/api/download")
async def api_download(req: DownloadRequest):
    if not req.url.strip():
        raise HTTPException(status_code=400, detail="URL不能为空")

    try:
        # Check if this is a fallback (Evil0ctal) parse result
        cached = _parsed_cache.get(req.url)
        if cached and cached.get("_fallback"):
            video_url = cached.get("_video_url", "")
            if not video_url:
                raise HTTPException(status_code=400, detail="无可用下载链接")
            task_id = video_service.start_fallback_download(video_url)
            return {"task_id": task_id}

        # Normal yt-dlp download
        if not req.format_id.strip():
            raise HTTPException(status_code=400, detail="format_id不能为空")
        task_id = video_service.start_download(req.url, req.format_id)
        return {"task_id": task_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"下载启动失败: {str(e)}")


@router.get("/api/download/status/{task_id}")
async def api_download_status(task_id: str):
    info = video_service.get_status(task_id)
    if not info:
        raise HTTPException(status_code=404, detail="任务不存在")
    response = {k: v for k, v in info.items() if k != "filepath"}
    return response


@router.get("/api/download/file/{task_id}")
async def api_download_file(task_id: str):
    import os

    filepath = video_service.get_filepath(task_id)
    if not filepath or not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="文件不存在或未下载完成")

    filename = os.path.basename(filepath)
    return FileResponse(
        filepath,
        media_type="video/mp4",
        filename=filename,
    )


@router.get("/api/proxy/image")
async def api_proxy_image(url: str):
    if not url:
        raise HTTPException(status_code=400, detail="url参数不能为空")
    try:
        # 封面域名（i.ytimg.com / i0.hdslb.com）在国内同样需要代理，
        # 不走代理会直接 ConnectTimeout。
        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            proxy=config.PROXY or None,
        ) as client:
            resp = await client.get(
                url,
                headers={"Referer": url, "User-Agent": "Mozilla/5.0"},
            )
            resp.raise_for_status()
        content_type = resp.headers.get("content-type", "image/jpeg")
        return StreamingResponse(
            iter([resp.content]),
            media_type=content_type,
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except Exception as e:
        # httpx 的 ConnectTimeout 等异常 str() 可能为空，带上类型便于排查
        raise HTTPException(status_code=400, detail=f"图片获取失败: {type(e).__name__}: {e}")


# ============ AI Summarization Endpoints ============

def _summarize_worker(task_id: str, url: str, subtitle_lang: str | None):
    """Worker thread for AI summarization."""
    try:
        ai_task_progress[task_id]["status"] = "transcribing"
        ai_task_progress[task_id]["message"] = "正在提取字幕..."

        # 1. Extract video title
        info = video_service.parse_video(url)
        title = info.get("title", "未知视频")

        # 2. Get subtitle text
        subtitle_data = subtitle_service.get_subtitle_data(url, subtitle_lang)
        transcript = "\n".join(item["text"] for item in subtitle_data) if subtitle_data else None
        if not transcript or not transcript.strip():
            ai_task_progress[task_id].update({
                "status": "error",
                "error": "该视频没有字幕，暂不支持 AI 总结",
            })
            return

        ai_task_progress[task_id].update({
            "status": "summarizing",
            "message": "正在 AI 总结...",
            "transcript": transcript,
            "subtitle_data": subtitle_data,
            "title": title,
        })

        # 3. AI Summarize
        result = ai_service.summarize(transcript, title)

        # 4. Generate mindmap markdown
        mindmap_md = ai_service.generate_mindmap_markdown(result, title)

        ai_task_progress[task_id].update({
            "status": "done",
            "result": result,
            "mindmap_markdown": mindmap_md,
        })

    except Exception as e:
        logger.error(f"[{task_id}] AI 总结失败: {e}")
        ai_task_progress[task_id].update({
            "status": "error",
            "error": f"AI 总结失败: {str(e)}",
        })


@router.post("/api/ai/summarize")
async def api_ai_summarize(req: SummarizeRequest):
    if not req.url.strip():
        raise HTTPException(status_code=400, detail="URL不能为空")

    task_id = uuid.uuid4().hex[:12]
    ai_task_progress[task_id] = {
        "status": "preparing",
        "message": "准备中...",
        "result": None,
        "transcript": None,
        "title": None,
        "mindmap_markdown": None,
        "error": None,
    }

    t = threading.Thread(
        target=_summarize_worker,
        args=(task_id, req.url, req.subtitle_lang),
        daemon=True,
    )
    t.start()

    return {"task_id": task_id}


@router.get("/api/ai/summarize/status/{task_id}")
async def api_ai_summarize_status(task_id: str):
    info = ai_task_progress.get(task_id)
    if not info:
        raise HTTPException(status_code=404, detail="任务不存在")

    response = {
        "status": info["status"],
        "message": info.get("message", ""),
        "error": info.get("error"),
    }
    if info["status"] == "done":
        response["result"] = info["result"]
        response["transcript"] = info.get("transcript", "")
        response["subtitle_data"] = info.get("subtitle_data", [])
        response["mindmap_markdown"] = info.get("mindmap_markdown", "")
        response["title"] = info.get("title", "")
    return response


@router.post("/api/ai/chat")
async def api_ai_chat(req: ChatRequest):
    if not req.messages:
        raise HTTPException(status_code=400, detail="消息不能为空")
    if not req.transcript_context:
        raise HTTPException(status_code=400, detail="缺少视频字幕上下文")

    try:
        reply = await asyncio.to_thread(
            ai_service.chat, req.transcript_context, req.messages
        )
        return {"message": {"role": "assistant", "content": reply}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 对话失败: {str(e)}")


def _content_disposition(filename: str) -> str:
    """构造 Content-Disposition 头。

    Starlette 用 latin-1 编码响应头，中文标题会直接抛 UnicodeEncodeError。
    按 RFC 5987 对文件名做百分号编码，保证头部是纯 ASCII。
    """
    safe = re.sub(r'[\\/:*?"<>|\r\n]+', "_", filename).strip() or "export"
    return f"attachment; filename*=UTF-8''{quote(safe[:50])}"


@router.get("/api/ai/export/{task_id}")
async def api_ai_export(task_id: str, format: str = "markdown"):
    info = ai_task_progress.get(task_id)
    if not info or info["status"] != "done":
        raise HTTPException(status_code=404, detail="总结结果不存在")

    result = info["result"]
    title = info.get("title", "视频总结")

    if format == "pdf":
        from services.export_service import generate_pdf
        pdf_bytes = generate_pdf(result, title)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": _content_disposition(f"{title[:50]}.pdf")},
        )

    # Default: markdown
    md_content = _result_to_markdown(result, title)
    return StreamingResponse(
        io.BytesIO(md_content.encode("utf-8")),
        media_type="text/markdown",
        headers={"Content-Disposition": _content_disposition(f"{title[:50]}.md")},
    )


def _result_to_markdown(result: dict, title: str) -> str:
    """将结构化结果转为 Markdown 文本。"""
    lines = [f"# {title}", ""]

    lines.append("## 摘要")
    lines.append(result.get("summary", ""))
    lines.append("")

    highlights = result.get("highlights", [])
    if highlights:
        lines.append("## 亮点")
        for h in highlights:
            ts = h.get("timestamp", "")
            point = h.get("point", "")
            lines.append(f"- [{ts}] {point}")
        lines.append("")

    terms = result.get("terms", [])
    if terms:
        lines.append("## 术语解释")
        for t in terms:
            lines.append(f"- **{t.get('term', '')}**: {t.get('explanation', '')}")
        lines.append("")

    qa = result.get("qa", [])
    if qa:
        lines.append("## 思考")
        for i, q in enumerate(qa, 1):
            lines.append(f"### {i}. {q.get('question', '')}")
            lines.append(q.get("answer", ""))
            lines.append("")

    return "\n".join(lines)
