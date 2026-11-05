import asyncio
import io
import os
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
from services import thumb_service
from services import ai_service
import httpx

logger = logging.getLogger("ai_router")

ai_task_progress: dict = {}

router = APIRouter()


class ParseRequest(BaseModel):
    url: str


class DownloadRequest(BaseModel):
    url: str
    format_id: str


class HistoryDownloadRequest(BaseModel):
    format_id: str | None = None


class SummarizeRequest(BaseModel):
    url: str
    subtitle_lang: str | None = None
    # 可选：AI 结果要回写到哪条历史记录。缺省时后端按 url 兜底匹配。
    history_id: int | None = None


class ChatRequest(BaseModel):
    # url 不参与对话：上下文只有字幕。历史记录没有可靠的链接上下文
    # （可能是短链甚至已失效），所以这里不要求调用方提供 url。
    url: str = ""
    messages: list[dict]
    transcript_context: str


@router.post("/api/parse")
async def api_parse(req: ParseRequest):
    if not req.url.strip():
        raise HTTPException(status_code=400, detail="URL不能为空")
    try:
        url = req.url.strip()
        result = await asyncio.to_thread(video_service.parse_video, url)
        # 解析成功即入库。落库失败（磁盘满等）只记日志，不阻断主流程：
        # 历史记录是辅助能力，解析结果照常返回（仅少一个 history_id）。
        try:
            history_id = history_service.upsert_parsed(url, result)
        except Exception as e:
            logger.error(f"历史记录落库失败（{url}）: {type(e).__name__}: {e}")
            history_id = None
        if history_id is not None:
            result = {**result, "history_id": history_id}
            # 封面缓存放后台线程：解析本身已经花了十几秒，不能再让下载拖住响应
            _schedule_thumb_cache(history_id, result.get("thumbnail"))
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"解析失败: {str(e)}")


def _schedule_thumb_cache(record_id: int, thumbnail_url: str) -> None:
    """后台线程缓存封面，不阻塞 /api/parse 的响应。"""
    if not thumbnail_url:
        return
    threading.Thread(
        target=_thumb_worker,
        args=(record_id, thumbnail_url),
        daemon=True,
    ).start()


def _thumb_worker(record_id: int, thumbnail_url: str) -> None:
    """封面缓存 worker：失败只记日志，解析结果早已返回，不受影响。"""
    try:
        rel_path = thumb_service.download_thumb(thumbnail_url, record_id)
        if rel_path:
            history_service.set_thumb_path(record_id, rel_path)
    except Exception as e:
        logger.error(f"封面缓存失败（record={record_id}）: {type(e).__name__}: {e}")


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

    {record_id} 是 int，匹配不到 /api/history/thumb/{id} 这类非数字路径，
    两个路由不会互相抢请求。
    """
    record = history_service.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
    return record


@router.get("/api/history/{record_id}/export")
async def api_history_export(record_id: int, format: str = "markdown"):
    """导出记录的 AI 总结（Markdown / PDF）。

    历史记录没有内存里的 task_id，用不了 /api/ai/export/{task_id}；
    这里按记录取 ai_result，复用同一套转换与导出逻辑。
    """
    record = history_service.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    result = record.get("ai_result")
    if not result:
        raise HTTPException(status_code=400, detail="该记录还没有 AI 总结，无法导出")

    title = record.get("title") or "视频总结"

    return _export_response(result, title, format)


def _export_response(result: dict, title: str, format: str) -> StreamingResponse:
    """把 AI 结果导出成 Markdown / PDF 响应。

    历史记录导出与 AI 任务导出用的是同一套转换与下载逻辑，只是数据来源不同
    （一个按记录 id 取库里的结果，一个取内存里的任务结果），所以分支收敛到这里，
    两个端点共用。
    """
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


@router.post("/api/history/{record_id}/download")
async def api_history_download(record_id: int, req: HistoryDownloadRequest | None = None):
    """从历史记录重新下载：用记录里的链接与清晰度重新走一遍网络下载。

    与首页下载共用同一套「拿下载地址」的判定，交互也完全一致：
    返回 task_id，前端用现有的 /api/download/status 与 /api/download/file 取进度和文件。
    """
    record = history_service.get_record(record_id)
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")

    url = (record.get("url") or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="该记录缺少视频链接")

    format_id = ((req.format_id if req else None) or "").strip()
    if not format_id:
        # 没指定清晰度就用记录里分辨率最高的一档（挑选逻辑在服务层）
        format_id = history_service.pick_best_format(record.get("formats") or [])
    if not format_id:
        raise HTTPException(status_code=400, detail="该记录没有可用的清晰度")

    # 走直链还是走 yt-dlp：和首页下载共用同一套判定
    try:
        mode, direct_url = await asyncio.to_thread(
            video_service.resolve_download_source, url, format_id
        )
    except Exception as e:
        # 源失效（视频下架 / 链接过期）：给出明确提示。这条历史记录不动，
        # 用户还能查详情、自己删。
        raise HTTPException(
            status_code=400,
            detail=f"视频源已失效或无法解析: {type(e).__name__}: {e}",
        )
    if mode == "direct":
        if not direct_url:
            raise HTTPException(status_code=400, detail="无可用下载链接")
        task_id = video_service.start_fallback_download(direct_url)
    else:
        task_id = video_service.start_download(url, format_id)
    return {"task_id": task_id}


@router.get("/api/history/thumb/{record_id}")
async def api_history_thumb(record_id: int):
    """本地缓存的封面。文件不存在返回 404，前端回退远程代理图。"""
    path = thumb_service.thumb_abs_path(record_id)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="封面不存在")
    return FileResponse(
        path,
        media_type=thumb_service.guess_media_type(path),
        headers={"Cache-Control": "public, max-age=86400"},
    )


@router.delete("/api/history/{record_id}")
async def api_history_delete(record_id: int):
    """删除单条历史记录，连同它的本地封面文件。"""
    if not history_service.delete_record(record_id):
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"deleted": True}


@router.delete("/api/history")
async def api_history_clear():
    """清空全部历史记录，连同所有本地封面文件。"""
    return {"deleted": history_service.clear_records()}


@router.post("/api/download")
async def api_download(req: DownloadRequest):
    if not req.url.strip():
        raise HTTPException(status_code=400, detail="URL不能为空")

    try:
        # 走直链还是走 yt-dlp：与历史记录下载共用同一套判定。
        # 判定里会重新解析一次，服务重启后抖音视频照样能拿到新直链。
        mode, direct_url = await asyncio.to_thread(
            video_service.resolve_download_source, req.url, req.format_id
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"视频源已失效或无法解析: {type(e).__name__}: {e}",
        )

    try:
        if mode == "direct":
            if not direct_url:
                raise HTTPException(status_code=400, detail="无可用下载链接")
            task_id = video_service.start_fallback_download(direct_url)
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

def _summarize_worker(task_id: str, url: str, subtitle_lang: str | None, record_id: int | None = None):
    """Worker thread for AI summarization.

    record_id 指向要回写的历史记录；为 None 时只跑 AI，不写库。
    """
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
            _fail_ai_task(task_id, record_id, "该视频没有字幕，暂不支持 AI 总结")
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

        _done_ai_task(task_id, record_id, subtitle_data, transcript, result, mindmap_md)

    except Exception as e:
        logger.error(f"[{task_id}] AI 总结失败: {e}")
        _fail_ai_task(task_id, record_id, f"AI 总结失败: {str(e)}")


def _done_ai_task(task_id, record_id, subtitle_data, transcript, result, mindmap_md):
    """AI 成功：先把结果写回历史记录，再把任务标记为完成。

    先写库后置状态：轮询看到 done 的那一刻，数据已经在库里了。
    """
    if record_id is not None:
        try:
            history_service.attach_ai_result(
                record_id, subtitle_data, transcript, result, mindmap_md
            )
        except Exception as e:
            logger.error(f"[{task_id}] AI 结果入库失败（record={record_id}）: {type(e).__name__}: {e}")

    ai_task_progress[task_id].update({
        "status": "done",
        "result": result,
        "mindmap_markdown": mindmap_md,
    })


def _fail_ai_task(task_id, record_id, error):
    """AI 失败：记录标记为 ai_failed 并保留失败原因，任务状态置为 error。"""
    if record_id is not None:
        try:
            history_service.mark_ai_failed(record_id, error)
        except Exception as e:
            logger.error(f"[{task_id}] AI 失败状态落库失败（record={record_id}）: {type(e).__name__}: {e}")

    ai_task_progress[task_id].update({
        "status": "error",
        "error": error,
    })


def _resolve_record_id(history_id: int | None, url: str) -> int | None:
    """确定 AI 结果回写到哪条记录。

    有 history_id 就用它；没有就按 url 兜底匹配最近一条记录，
    匹配不到就不写库（不影响 AI 任务本身）。
    """
    if history_id is not None:
        return history_id
    try:
        return history_service.get_record_by_url(url)
    except Exception as e:
        logger.error(f"按 url 匹配历史记录失败（{url}）: {type(e).__name__}: {e}")
        return None


@router.post("/api/ai/summarize")
async def api_ai_summarize(req: SummarizeRequest):
    if not req.url.strip():
        raise HTTPException(status_code=400, detail="URL不能为空")

    record_id = _resolve_record_id(req.history_id, req.url)

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
        args=(task_id, req.url, req.subtitle_lang, record_id),
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
    # 全是空白的问题等于没问：同样不该发给模型
    if not req.messages or not any(
        (m.get("content") or "").strip() for m in req.messages
    ):
        raise HTTPException(status_code=400, detail="消息不能为空")
    # 只有空白的上下文等同于没有：不能拿着空上下文去问模型，
    # 要么明确报错，要么由前端先给出提示。
    transcript = (req.transcript_context or "").strip()
    if not transcript:
        raise HTTPException(status_code=400, detail="缺少视频字幕上下文")

    try:
        reply = await asyncio.to_thread(
            ai_service.chat, transcript, req.messages
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

    return _export_response(result, title, format)


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
