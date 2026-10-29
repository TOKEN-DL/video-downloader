import re
import logging
import httpx
from yt_dlp import YoutubeDL
import config
from services.video_service import _YTDL_LOGGER, _retry_sleep

logger = logging.getLogger("subtitle_service")

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
}

# 字幕文件多托管在 YouTube/GoogleVideo 等必须走代理的域名上，
# 直连会 WinError 10060 超时。这里统一复用 config.PROXY。
_PROXY = config.PROXY or None


def _fmt_time(seconds: float) -> str:
    """将秒数格式化为 MM:SS。"""
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}:{s:02d}"


def get_subtitle_text(url: str, lang: str = None) -> str | None:
    """提取视频字幕并返回清洗后的纯文本。无字幕返回 None。"""
    data = get_subtitle_data(url, lang)
    if not data:
        return None
    lines = [item["text"] for item in data]
    return "\n".join(lines)


def get_subtitle_data(url: str, lang: str = None) -> list[dict] | None:
    """提取视频字幕并返回带时间戳的结构化数据 [{time, text}]。无字幕返回 None。"""
    if "bilibili.com" in url or "b23.tv" in url:
        try:
            data = _extract_bilibili_subtitle_data(url, lang)
            if data:
                return data
        except Exception as e:
            logger.warning(f"B站字幕提取失败，降级到 yt-dlp: {e}")
    try:
        return _extract_via_info_data(url, lang)
    except Exception as e:
        logger.warning(f"字幕提取失败: {e}")
        return None


# ============ Bilibili Platform API ============

def _extract_bvid(url: str) -> tuple[str, int]:
    """从 URL 提取 bvid 和分 P 编号。返回 (bvid, page)。"""
    if "b23.tv" in url:
        resp = httpx.head(url, follow_redirects=True, timeout=10, headers=_HEADERS, proxy=_PROXY)
        url = str(resp.url)

    m = re.search(r"BV[a-zA-Z0-9]+", url)
    if not m:
        raise ValueError(f"无法从 URL 提取 bvid: {url}")

    bvid = m.group(0)
    pm = re.search(r"[?&]p=(\d+)", url)
    page = int(pm.group(1)) if pm else 1
    return bvid, page


def _get_bilibili_cid(bvid: str, page: int) -> tuple[int, int]:
    """通过 bvid 获取 aid 和 cid。返回 (aid, cid)。"""
    headers = {**_HEADERS, "Referer": f"https://www.bilibili.com/video/{bvid}"}
    resp = httpx.get(
        "https://api.bilibili.com/x/web-interface/view",
        params={"bvid": bvid},
        headers=headers,
        timeout=15,
        proxy=_PROXY,
    )
    resp.raise_for_status()
    data = resp.json().get("data") or {}
    aid = data.get("aid")
    cid = data.get("cid")
    if not aid or not cid:
        raise ValueError(f"获取 aid/cid 失败")
    pages = data.get("pages") or []
    if len(pages) > 1 and page > 1:
        idx = min(page - 1, len(pages) - 1)
        cid = pages[idx].get("cid", cid)
    return aid, cid


def _get_bilibili_subtitle_list(aid: int, cid: int, bvid: str) -> list[dict]:
    """通过弹幕接口获取 B站视频字幕轨道列表（无需 cookie）。"""
    headers = {**_HEADERS, "Referer": f"https://www.bilibili.com/video/{bvid}"}
    resp = httpx.get(
        "https://api.bilibili.com/x/v2/dm/view",
        params={"aid": aid, "oid": cid, "type": 1},
        headers=headers,
        timeout=15,
        proxy=_PROXY,
    )
    resp.raise_for_status()
    data = resp.json()
    subtitle_info = (data.get("data") or {}).get("subtitle") or {}
    return subtitle_info.get("subtitles") or []


def _pick_bilibili_subtitle(subtitles: list[dict], lang: str | None) -> dict | None:
    """从字幕轨道列表中选最佳字幕。"""
    if not subtitles:
        return None

    if lang and lang.startswith("zh"):
        priority = ["ai-zh", "zh-Hans", "zh-CN", "zh-Hant"]
    elif lang == "en":
        priority = ["ai-en", "en-US", "en"]
    else:
        priority = ["ai-zh", "zh-Hans", "zh-CN", "zh-Hant", "ai-en", "en-US", "en"]

    for p in priority:
        track = next((s for s in subtitles if s.get("lan") == p), None)
        if track:
            return track
    return subtitles[0]


def _download_bilibili_subtitle_data(subtitle_url: str) -> list[dict] | None:
    """下载并解析 B站字幕 JSON，返回 [{time, text}]。"""
    if subtitle_url.startswith("//"):
        subtitle_url = "https:" + subtitle_url

    resp = httpx.get(subtitle_url, headers=_HEADERS, timeout=15, proxy=_PROXY)
    resp.raise_for_status()
    data = resp.json()

    body = data.get("body") or []
    if not body:
        return None

    lines = []
    prev = None
    for item in body:
        text = (item.get("content") or "").strip()
        if not text or text == prev:
            continue
        prev = text
        start = float(item.get("from", 0))
        lines.append({"time": _fmt_time(start), "text": text})
    return lines if lines else None


def _extract_bilibili_subtitle_data(url: str, lang: str | None) -> list[dict] | None:
    """通过 Bilibili 弹幕 API 提取带时间戳字幕（无需 cookie）。"""
    bvid, page = _extract_bvid(url)
    aid, cid = _get_bilibili_cid(bvid, page)
    subtitles = _get_bilibili_subtitle_list(aid, cid, bvid)
    track = _pick_bilibili_subtitle(subtitles, lang)
    if not track:
        return None
    subtitle_url = track.get("subtitle_url")
    if not subtitle_url:
        return None
    return _download_bilibili_subtitle_data(subtitle_url)


# ============ yt-dlp Generic ============

def _extract_via_info_data(url: str, lang: str | None) -> list[dict] | None:
    """通过 yt-dlp 获取字幕 URL，下载并返回 [{time, text}]。"""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "ffmpeg_location": config.FFMPEG_PATH,
        "skip_download": True,
        "socket_timeout": config.YT_SOCKET_TIMEOUT,
        "retries": config.YT_RETRIES,
        "fragment_retries": config.YT_FRAGMENT_RETRIES,
        "retry_sleep": {"http": _retry_sleep, "fragment": _retry_sleep},
        "logger": _YTDL_LOGGER,
    }
    if config.PROXY:
        opts["proxy"] = config.PROXY
    if config.JS_RUNTIMES:
        opts["js_runtimes"] = config.JS_RUNTIMES
    opts["remote_components"] = set(config.YT_REMOTE_COMPONENTS)

    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    manual = info.get("subtitles", {})
    auto = info.get("automatic_captions", {})

    target_lang = lang or "zh"
    lang_order = [target_lang]
    if target_lang != "en":
        lang_order.append("en")
    if target_lang == "zh":
        lang_order.extend(["zh-Hans", "zh-Hant"])

    for source in [manual, auto]:
        for l in lang_order:
            tracks = source.get(l, [])
            data = _download_subtitle_track_data(tracks)
            if data:
                return data

    return None


def _download_subtitle_track_data(tracks: list[dict]) -> list[dict] | None:
    """从字幕轨道列表中下载并解析为 [{time, text}]。"""
    for fmt in ["json3", "srv1", "srv2", "srv3"]:
        track = next((t for t in tracks if t.get("ext") == fmt), None)
        if not track or not track.get("url"):
            continue
        try:
            resp = httpx.get(track["url"], follow_redirects=True, timeout=30, proxy=_PROXY)
            if resp.status_code != 200 or not resp.text.strip():
                continue
            if fmt == "json3":
                return _parse_json3_data(resp.text)
            return _parse_xml_subtitle_data(resp.text)
        except Exception as e:
            logger.warning(f"字幕下载失败 ({fmt}): {e}")
            continue
    return None


def _parse_json3_data(raw: str) -> list[dict] | None:
    """解析 YouTube json3 字幕格式，返回 [{time, text}]。"""
    import json
    data = json.loads(raw)
    lines = []
    for event in data.get("events", []):
        segs = event.get("segs")
        if not segs:
            continue
        text = "".join(s.get("utf8", "") for s in segs).strip()
        if text and text != "\n":
            text = re.sub(r"<[^>]+>", "", text).strip()
            if text:
                start_ms = event.get("tStartMs", 0) or 0
                lines.append({"time": _fmt_time(start_ms / 1000), "text": text})

    # Deduplicate consecutive lines
    result = []
    prev = None
    for item in lines:
        if item["text"] != prev:
            result.append(item)
            prev = item["text"]
    return result if result else None


def _parse_xml_subtitle_data(raw: str) -> list[dict] | None:
    """解析 srv1/srv2 XML 字幕格式，返回 [{time, text}]。"""
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return None

    lines = []
    for elem in root.iter():
        if elem.text and elem.text.strip():
            text = re.sub(r"<[^>]+>", "", elem.text).strip()
            if text:
                start = float(elem.get("start", 0))
                lines.append({"time": _fmt_time(start), "text": text})

    result = []
    prev = None
    for item in lines:
        if item["text"] != prev:
            result.append(item)
            prev = item["text"]
    return result if result else None
