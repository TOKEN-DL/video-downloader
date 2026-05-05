import re
import json
import logging
import urllib.parse
import requests

logger = logging.getLogger("douyin_service")

_MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
)


def _resolve_short_url(url: str) -> str:
    if "v.douyin.com" not in url:
        return url
    try:
        current = url
        for _ in range(5):
            resp = requests.get(current, headers={"User-Agent": _MOBILE_UA},
                                allow_redirects=False, timeout=10)
            location = resp.headers.get("location")
            if not location:
                break
            if not location.startswith("http"):
                location = urllib.parse.urljoin(current, location)
            if "douyin.com/video/" in location or "douyin.com/note/" in location:
                return location
            current = location
    except Exception as e:
        logger.warning(f"Failed to resolve short URL: {e}")
    return url


def _get_video_id(url: str) -> str | None:
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    for key in ("vid", "id", "modal_id"):
        val = params.get(key, [None])[0]
        if val:
            return val
    segments = parsed.path.strip("/").split("/")
    if segments:
        return segments[-1]
    return None


def _fetch_video_info(aweme_id: str) -> dict | None:
    share_url = f"https://www.iesdouyin.com/share/video/{aweme_id}/"
    try:
        resp = requests.get(share_url, headers={"User-Agent": _MOBILE_UA}, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to fetch iesdouyin page: {e}")
        return None

    m = re.search(r"window\._ROUTER_DATA\s*=\s*({.*?})\s*;?\s*</script>", resp.text, re.DOTALL)
    if not m:
        logger.warning("No _ROUTER_DATA found in iesdouyin page")
        return None

    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse _ROUTER_DATA: {e}")
        return None

    loader = data.get("loaderData", {})
    for key, val in loader.items():
        if not val or not isinstance(val, dict):
            continue
        vir = val.get("videoInfoRes")
        if not vir:
            continue
        items = vir.get("item_list", [])
        if items:
            return items[0]

    logger.warning("No video data in iesdouyin response")
    return None


def _extract_video_url(item: dict) -> str | None:
    video = item.get("video", {})
    play_addr = video.get("play_addr", {})
    urls = play_addr.get("url_list", [])
    if urls:
        # Use the last URL which is usually the direct video link
        return urls[-1]
    return None


def _extract_cover(item: dict) -> str | None:
    video = item.get("video", {})
    for key in ("cover", "dynamic_cover", "origin_cover"):
        cover = video.get(key, {})
        urls = cover.get("url_list", []) if isinstance(cover, dict) else []
        if urls:
            return urls[0]
    return None


def parse_video(url: str) -> dict | None:
    resolved = _resolve_short_url(url)
    aweme_id = _get_video_id(resolved)
    if not aweme_id:
        logger.warning(f"Cannot extract video ID from URL: {url}")
        return None

    item = _fetch_video_info(aweme_id)
    if not item:
        return None

    video_url = _extract_video_url(item)
    if not video_url:
        logger.warning("No video URL found in item data")
        return None

    # Remove watermark: replace playwm with play
    video_url = video_url.replace("/playwm/", "/play/")

    author_info = item.get("author", {})
    title = item.get("desc", "")
    thumbnail = _extract_cover(item)
    author = author_info.get("nickname", "")
    duration = item.get("duration")
    if duration:
        duration = duration / 1000

    return {
        "title": title,
        "thumbnail": thumbnail or "",
        "duration": duration,
        "author": author,
        "platform": "douyin",
        "formats": [
            {
                "format_id": "fallback_best",
                "resolution": "best",
                "ext": "mp4",
                "filesize": None,
            }
        ],
        "subtitles": [],
        "_fallback": True,
        "_video_url": video_url,
    }
