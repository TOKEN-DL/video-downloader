from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.video_service import parse_video, start_download, get_status, get_filepath

router = APIRouter()


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
        result = parse_video(req.url)
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"解析失败: {str(e)}")


@router.post("/api/download")
async def api_download(req: DownloadRequest):
    if not req.url.strip() or not req.format_id.strip():
        raise HTTPException(status_code=400, detail="URL和格式ID不能为空")
    try:
        task_id = start_download(req.url, req.format_id)
        return {"task_id": task_id}
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
    from fastapi.responses import FileResponse
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
