import os
import uuid
import logging
import asyncio
import threading
import time
import traceback
from typing import Optional
from yt_dlp import YoutubeDL
import config

logger = logging.getLogger("video_service")
logger.setLevel(logging.DEBUG)

task_progress: dict = {}

# 解析结果缓存：url -> (缓存时间, 结果)
_parse_cache: dict = {}


class _YtdlLogger:
    """把 yt-dlp 的日志导向 Python logging，而不是直接写 stdout。

    服务常驻时（尤其是 uvicorn 热重载的子进程），stdout 句柄可能已失效，
    此时 yt-dlp 写 stdout 会抛 OSError [Errno 22] Invalid argument，
    整个下载任务会被打断。走 logging 则统一落到 backend/logs/app.log。
    """

    def debug(self, msg):
        logger.debug(f"yt-dlp: {msg}")

    def info(self, msg):
        logger.info(f"yt-dlp: {msg}")

    def warning(self, msg):
        logger.warning(f"yt-dlp: {msg}")

    def error(self, msg):
        logger.error(f"yt-dlp: {msg}")


_YTDL_LOGGER = _YtdlLogger()

# ---------------------------------------------------------------------------
# 格式选择器
#
# yt-dlp 的 `best` / `b` 语义是「单个已合并的音视频文件」。B站走 DASH，
# 只有视频单轨（30016 等）和音频单轨（30280 等），根本不存在合并流，
# 于是 `best` 必然选不中任何格式，直接抛：
#     [BiliBili] BVxxxx: Requested format is not available
# 所以这里一律用显式的「视频轨 + 音频轨」选择器。
#
# 视频轨优先 h264(avc1)：yt-dlp 默认排序会挑 AV1(av01)，AV1 塞进 mp4
# 容器后部分播放器/剪辑软件解码吃力，而 h264 兼容性最好。
# 高度限制在 720p 是为了兜底时不至于拉下几百 MB 的大文件。
# ---------------------------------------------------------------------------
_VIDEO_TRACK = "bv[height<=720][vcodec^=avc1]"
_AUDIO_TRACK = "ba"


def _retry_sleep(attempts: int) -> int:
    """指数退避：代理链路瞬时断开时，给对方留出恢复时间。"""
    return min(config.YT_RETRY_SLEEP_MAX, 2 ** min(attempts, 5))


def _build_opts() -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "ffmpeg_location": config.FFMPEG_PATH,
        "socket_timeout": config.YT_SOCKET_TIMEOUT,
        "retries": config.YT_RETRIES,
        "fragment_retries": config.YT_FRAGMENT_RETRIES,
        "retry_sleep": {"http": _retry_sleep, "fragment": _retry_sleep},
        "logger": _YTDL_LOGGER,
    }
    if config.YT_CONTINUEDL:
        opts["continuedl"] = True
    if config.PROXY:
        opts["proxy"] = config.PROXY
    if config.JS_RUNTIMES:
        opts["js_runtimes"] = config.JS_RUNTIMES
    opts["remote_components"] = set(config.YT_REMOTE_COMPONENTS)
    return opts


def _run_async_in_thread(coro):
    """Run an async coroutine in a separate thread to avoid event loop conflicts."""
    result = [None]
    exc = [None]

    def _target():
        loop = asyncio.new_event_loop()
        try:
            result[0] = loop.run_until_complete(coro)
        except Exception as e:
            exc[0] = e
        finally:
            loop.close()

    t = threading.Thread(target=_target)
    t.start()
    t.join()
    if exc[0]:
        raise exc[0]
    return result[0]


def parse_video(url: str) -> dict:
    """解析视频信息。同一 URL 在缓存有效期内直接返回上次结果。"""
    if config.PARSE_CACHE_TTL <= 0:
        return _parse_uncached(url)

    cached = _parse_cache.get(url)
    if cached and (time.time() - cached[0]) < config.PARSE_CACHE_TTL:
        logger.info(f"命中解析缓存: {url}")
        return cached[1]

    result = _parse_uncached(url)

    _parse_cache[url] = (time.time(), result)
    if len(_parse_cache) > config.PARSE_CACHE_MAX:
        stale = sorted(_parse_cache.items(), key=lambda kv: kv[1][0])
        for key, _ in stale[: len(_parse_cache) - config.PARSE_CACHE_MAX]:
            _parse_cache.pop(key, None)
    return result


def _parse_uncached(url: str) -> dict:
    try:
        return _parse_with_ytdlp(url)
    except Exception as e:
        err_msg = str(e)
        if "Fresh cookies" in err_msg or "Douyin" in err_msg or "douyin" in err_msg.lower():
            logger.warning(f"yt-dlp failed for Douyin-like URL, trying local parser: {err_msg}")
            from services.douyin_service import parse_video as douyin_parse
            result = douyin_parse(url)
            if result:
                return result
        raise


def _parse_with_ytdlp(url: str) -> dict:
    opts = _build_opts()
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    formats = []
    seen = set()
    for f in info.get("formats", []):
        height = f.get("height")
        ext = f.get("ext", "")
        if not height or ext not in ("mp4", "webm", "mkv"):
            continue
        if f.get("vcodec", "none") == "none":
            continue
        res_label = f"{height}p"
        if res_label in seen:
            continue
        seen.add(res_label)
        filesize = f.get("filesize") or f.get("filesize_approx")
        formats.append({
            "format_id": f["format_id"],
            "resolution": res_label,
            "ext": ext,
            "filesize": filesize,
        })

    formats.sort(key=lambda x: int(x["resolution"].rstrip("p")), reverse=True)

    subtitles = []
    subs = info.get("subtitles", {})
    auto_subs = info.get("automatic_captions", {})
    for lang, tracks in subs.items():
        subtitles.append({"lang": lang, "name": lang, "auto_generated": False})
    for lang, tracks in auto_subs.items():
        if not any(s["lang"] == lang for s in subtitles):
            subtitles.append({"lang": lang, "name": f"{lang} (自动)", "auto_generated": True})

    return {
        "title": info.get("title", ""),
        "thumbnail": info.get("thumbnail", ""),
        "duration": info.get("duration"),
        "author": info.get("uploader", info.get("channel", "")),
        "platform": info.get("extractor_key", "").replace("IE", "").lower(),
        "formats": formats,
        "subtitles": subtitles,
    }


def _progress_hook(task_id: str):
    def hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes", 0)
            speed = d.get("speed")
            eta = d.get("eta")
            task_progress[task_id].update({
                "status": "downloading",
                "progress": round(downloaded / total * 100, 1) if total else None,
                "downloaded": downloaded,
                "total": total,
                "speed": f"{speed / 1024 / 1024:.1f}MB/s" if speed else None,
                "eta": eta,
            })
        elif d["status"] == "finished":
            task_progress[task_id].update({
                "status": "merging",
                "progress": 100,
            })
    return hook


def _requested_height(url: str, format_id: str) -> Optional[int]:
    """从解析缓存里取用户所选格式的分辨率（像素高）。

    前端解析与下载用的是同一个 URL 字符串，缓存通常命中；命中不了返回
    None，兜底逻辑会退到固定策略。
    """
    entry = _parse_cache.get(url)
    if not entry:
        return None
    for fmt in entry[1].get("formats", []):
        if fmt.get("format_id") == format_id:
            try:
                return int(str(fmt.get("resolution", "")).rstrip("p"))
            except ValueError:
                return None
    return None


def _build_rescue_format(url: str, format_id: str) -> str:
    """构造兜底格式选择器（按优先级排列，yt-dlp 会依次尝试）。

    1. 同分辨率、不限定编码：yt-dlp 默认排序会挑 AV1，体积更小且是另一条
       CDN 路径；重新解析也会拿到新的签名 URL。
    2. ≤720p 的 h264：兼容性最好的通用兜底。
    3. 最佳视频轨 + 最佳音频轨：最后手段。
    """
    cands = []
    height = _requested_height(url, format_id)
    if height:
        cands.append(f"bv[height<={height}]+{_AUDIO_TRACK}")
    cands.append(f"{_VIDEO_TRACK}+{_AUDIO_TRACK}")
    cands.append(f"bv*+{_AUDIO_TRACK}")
    return "/".join(cands)


def _download_worker(url: str, format_id: str, task_id: str, output_path: str):
    task_progress[task_id] = {
        "status": "downloading",
        "progress": 0,
        "speed": None,
        "downloaded": 0,
        "total": None,
        "eta": None,
        "filepath": None,
    }

    rescue_fmt = _build_rescue_format(url, format_id)

    # 主流程：指定清晰度 + 最佳音轨；若 format_id 已失效（换了清晰度后
    # 旧 id 失效等），退到兜底组合，而不是退到必然失败的 `best`。
    format_str = f"{format_id}+bestaudio/{rescue_fmt}"
    logger.info(f"[{task_id}] Downloading {url} with format: {format_str}")
    logger.info(f"[{task_id}] ffmpeg_location: {config.FFMPEG_PATH}")

    try:
        try:
            _run_download(url, format_str, task_id, output_path)
        except Exception as e:
            # 合并流要下两个文件，任一失败就整条失败。若失败原因是网络抖动
            # （代理链路 SSL 断开 / 超时）或格式已失效，再试一次兜底组合——
            # 它会走另一条 CDN 路径，能把整条下载救回来。
            if not config.YT_DOWNLOAD_FALLBACK or not _is_rescuable_error(e):
                raise
            logger.warning(
                f"[{task_id}] 主下载失败（{type(e).__name__}），改用兜底格式重试一次: {e}"
            )
            task_progress[task_id].update(
                {"status": "downloading", "progress": 0, "error": None}
            )
            try:
                _run_download(url, rescue_fmt, task_id, output_path)
            except Exception as e2:
                # 保留首次失败的上下文：只报兜底那次的话，用户会看到
                # "Requested format is not available" 这种更让人困惑的错。
                raise RuntimeError(
                    f"主下载失败({type(e).__name__}: {e})；"
                    f"兜底下载也失败({type(e2).__name__}: {e2})"
                ) from e2
    except Exception as e:
        # 记录完整堆栈：只留 str(e) 会丢掉关键信息（如 OSError 来自哪一步）
        logger.error(f"[{task_id}] Download failed: {e}")
        logger.error(f"[{task_id}] 完整堆栈:\n{traceback.format_exc()}")
        task_progress[task_id]["status"] = "error"
        task_progress[task_id]["error"] = str(e)
        return

    task_progress[task_id]["status"] = "done"
    task_progress[task_id]["filepath"] = output_path
    logger.info(f"[{task_id}] Download complete: {output_path}")


_NETWORK_ERROR_MARKERS = (
    "UNEXPECTED_EOF_WHILE_READING",
    "SSLError",
    "SSL:",
    "Remote end closed",
    "Connection reset",
    "Connection aborted",
    "ConnectionRefused",
    "timed out",
    "TimeoutError",
    "IncompleteRead",
    "ChunkedEncodingError",
    "ReadTimeout",
    "ConnectTimeout",
    "EOF occurred in violation",
)


def _is_network_error(exc: Exception) -> bool:
    """判断异常是否属于可重试的网络类错误。"""
    text = f"{type(exc).__name__}: {exc}"
    return any(marker.lower() in text.lower() for marker in _NETWORK_ERROR_MARKERS)


# 格式类错误：指定的 format_id 已失效 / 该站点没有该格式。
# 这类错误重试同一个 format_id 没意义，但换一个组合（_build_rescue_format）有意义。
_FORMAT_ERROR_MARKERS = (
    "Requested format is not available",
    "No video formats found",
    "requested format not available",
)


def _is_rescuable_error(exc: Exception) -> bool:
    """判断异常是否值得用兜底格式再试一次。

    网络抖动：换个 CDN 路径重试有机会成功。
    格式失效：换一个可用的格式组合就能成功。
    """
    if _is_network_error(exc):
        return True
    text = f"{type(exc).__name__}: {exc}"
    return any(marker.lower() in text.lower() for marker in _FORMAT_ERROR_MARKERS)


def _run_download(url: str, format_str: str, task_id: str, output_path: str):
    """执行一次 yt-dlp 下载。"""
    opts = _build_opts()
    opts.update({
        "format": format_str,
        "outtmpl": output_path,
        "merge_output_format": "mp4",
        "progress_hooks": [_progress_hook(task_id)],
        # 日志交给 _YTDL_LOGGER 落文件，不写 stdout（见 _YtdlLogger 说明）
        "verbose": True,
    })

    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        # Log what was actually downloaded
        actual_format = info.get("format", "unknown")
        requested = info.get("requested_formats", [])
        if requested:
            for rf in requested:
                logger.info(f"[{task_id}] Downloaded stream: {rf.get('format')} "
                            f"vcodec={rf.get('vcodec')} acodec={rf.get('acodec')}")
        else:
            vcodec = info.get("vcodec", "none")
            acodec = info.get("acodec", "none")
            logger.info(f"[{task_id}] Single stream: format={actual_format} "
                        f"vcodec={vcodec} acodec={acodec}")

    # Verify the output file has audio
    _verify_audio(task_id, output_path)


def _verify_audio(task_id: str, filepath: str):
    """Verify the downloaded file contains audio stream."""
    try:
        import subprocess
        result = subprocess.run(
            [config.FFPROBE_PATH,
             "-v", "quiet", "-print_format", "json",
             "-show_streams", "-select_streams", "a", filepath],
            capture_output=True, text=True, timeout=10
        )
        import json
        data = json.loads(result.stdout)
        streams = data.get("streams", [])
        if streams:
            logger.info(f"[{task_id}] Audio verified: {streams[0].get('codec_name')} "
                        f"{streams[0].get('sample_rate')}Hz {streams[0].get('channels')}ch")
        else:
            logger.warning(f"[{task_id}] WARNING: No audio stream found in {filepath}")
    except Exception as e:
        logger.warning(f"[{task_id}] Could not verify audio: {e}")


def start_download(url: str, format_id: str) -> str:
    task_id = uuid.uuid4().hex[:12]
    output_path = os.path.join(config.DOWNLOAD_DIR, f"{task_id}.mp4")
    t = threading.Thread(target=_download_worker, args=(url, format_id, task_id, output_path), daemon=True)
    t.start()
    return task_id


def _fallback_download_worker(video_url: str, task_id: str, output_path: str):
    task_progress[task_id] = {
        "status": "downloading",
        "progress": 0,
        "speed": None,
        "downloaded": 0,
        "total": None,
        "eta": None,
        "filepath": None,
    }

    import time
    import httpx

    async def _do_download():
        start_time = time.time()
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            async with client.stream("GET", video_url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://www.douyin.com/",
            }) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0))
                downloaded = 0
                with open(output_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        elapsed = time.time() - start_time
                        speed = downloaded / elapsed if elapsed > 0 else 0
                        task_progress[task_id].update({
                            "status": "downloading",
                            "progress": round(downloaded / total * 100, 1) if total else None,
                            "downloaded": downloaded,
                            "total": total if total > 0 else None,
                            "speed": f"{speed / 1024 / 1024:.1f}MB/s" if speed else None,
                        })

    try:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_do_download())
        finally:
            loop.close()
        task_progress[task_id]["status"] = "done"
        task_progress[task_id]["filepath"] = output_path
        logger.info(f"[{task_id}] Fallback download complete: {output_path}")
    except Exception as e:
        logger.error(f"[{task_id}] Fallback download failed: {e}")
        task_progress[task_id]["status"] = "error"
        task_progress[task_id]["error"] = str(e)


def start_fallback_download(video_url: str) -> str:
    task_id = uuid.uuid4().hex[:12]
    output_path = os.path.join(config.DOWNLOAD_DIR, f"{task_id}.mp4")
    t = threading.Thread(target=_fallback_download_worker, args=(video_url, task_id, output_path), daemon=True)
    t.start()
    return task_id


def get_status(task_id: str) -> Optional[dict]:
    return task_progress.get(task_id)


def get_filepath(task_id: str) -> Optional[str]:
    info = task_progress.get(task_id)
    if info and info.get("status") == "done" and info.get("filepath"):
        return info["filepath"]
    return None
