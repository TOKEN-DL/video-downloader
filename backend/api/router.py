import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from services.video_service import parse_video, start_download, start_fallback_download, get_status, get_filepath
import httpx

router = APIRouter()

# Cache parsed video info for fallback downloads
_parsed_cache: dict = {}


class ParseRequest(BaseModel):
    url: str


class DownloadRequest(BaseModel):
    url: str
    format_id: str


@router.post("/api/parse")
async def api_parse(req: ParseRequest):
    if not req.url.strip():
        raise HTTPException(status_code=400, detail="URL不能为空")
    try:
        result = await asyncio.to_thread(parse_video, req.url)
        if result.get("_fallback"):
            _parsed_cache[req.url] = result
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"解析失败: {str(e)}")


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
            task_id = start_fallback_download(video_url)
            return {"task_id": task_id}

        # Normal yt-dlp download
        if not req.format_id.strip():
            raise HTTPException(status_code=400, detail="format_id不能为空")
        task_id = start_download(req.url, req.format_id)
        return {"task_id": task_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"下载启动失败: {str(e)}")


@router.get("/api/download/status/{task_id}")
async def api_download_status(task_id: str):
    info = get_status(task_id)
    if not info:
        raise HTTPException(status_code=404, detail="任务不存在")
    response = {k: v for k, v in info.items() if k != "filepath"}
    return response


@router.get("/api/download/file/{task_id}")
async def api_download_file(task_id: str):
    import os

    filepath = get_filepath(task_id)
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
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
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
        raise HTTPException(status_code=400, detail=f"图片获取失败: {str(e)}")
