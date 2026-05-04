import os
import uuid
import logging
import threading
from typing import Optional
from yt_dlp import YoutubeDL
import config

logger = logging.getLogger("video_service")

task_progress: dict = {}


def _build_opts() -> dict:
    opts = {"quiet": True, "no_warnings": True, "ffmpeg_location": config.FFMPEG_PATH}
    if config.PROXY:
        opts["proxy"] = config.PROXY
    return opts


def parse_video(url: str) -> dict:
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

    # First try: merge specific video + best audio
    # Fallback: best single format with audio
    format_str = f"{format_id}+bestaudio/best"
    logger.info(f"[{task_id}] Downloading {url} with format: {format_str}")
    logger.info(f"[{task_id}] ffmpeg_location: {config.FFMPEG_PATH}")

    opts = _build_opts()
    opts.update({
        "format": format_str,
        "outtmpl": output_path,
        "merge_output_format": "mp4",
        "progress_hooks": [_progress_hook(task_id)],
        "verbose": True,
    })

    try:
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

        task_progress[task_id]["status"] = "done"
        task_progress[task_id]["filepath"] = output_path
        logger.info(f"[{task_id}] Download complete: {output_path}")
    except Exception as e:
        logger.error(f"[{task_id}] Download failed: {e}")
        task_progress[task_id]["status"] = "error"
        task_progress[task_id]["error"] = str(e)


def _verify_audio(task_id: str, filepath: str):
    """Verify the downloaded file contains audio stream."""
    try:
        import subprocess
        result = subprocess.run(
            [config.FFMPEG_PATH.replace("ffmpeg", "ffprobe"),
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


def get_status(task_id: str) -> Optional[dict]:
    return task_progress.get(task_id)


def get_filepath(task_id: str) -> Optional[str]:
    info = task_progress.get(task_id)
    if info and info.get("status") == "done" and info.get("filepath"):
        return info["filepath"]
    return None
