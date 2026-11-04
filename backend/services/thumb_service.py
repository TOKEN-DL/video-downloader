"""历史记录封面本地缓存。

抖音 / B 站封面 URL 带签名会过期，历史记录隔几天回看就成裂图。解析成功后
把封面下载到本地缓存，列表页 / 详情页优先读本地封面，读不到再回退远程代理图。

本模块负责网络 IO 与文件 IO，**任何失败都只记日志、不抛异常**：封面缓存是
锦上添花，绝不能把 /api/parse 变成 500。
"""
import logging
import os

import httpx

import config

logger = logging.getLogger("thumb_service")

# 与 /api/proxy/image 同一套请求头策略：封面域名要带 Referer 才给图
THUMB_HEADERS = {"User-Agent": "Mozilla/5.0"}
THUMB_TIMEOUT = 15


def thumb_dir() -> str:
    """封面缓存目录（运行时从 config 读，测试才能指向临时目录）。"""
    return config.HISTORY_THUMB_DIR


def thumb_rel_path(record_id: int) -> str:
    """库中 thumb_path 列存的相对路径（相对 backend/history）。"""
    return f"thumbs/{record_id}.jpg"


def thumb_abs_path(record_id: int) -> str:
    """封面文件的绝对路径。"""
    return os.path.join(thumb_dir(), f"{record_id}.jpg")


def download_thumb(url: str, record_id: int) -> str | None:
    """下载封面到本地缓存。成功返回相对路径，失败返回 None（不抛异常）。"""
    if not url:
        return None

    target = thumb_abs_path(record_id)
    tmp = f"{target}.part"
    try:
        os.makedirs(thumb_dir(), exist_ok=True)
        with httpx.Client(
            timeout=THUMB_TIMEOUT,
            follow_redirects=True,
            proxy=config.PROXY or None,
        ) as client:
            resp = client.get(url, headers={"Referer": url, **THUMB_HEADERS})
            resp.raise_for_status()
            content = resp.content

        if not content:
            logger.warning(f"封面内容为空，跳过缓存 (record={record_id}, url={url})")
            return None

        # 先写 .part 再改名，避免半截文件被当成有效封面读出去
        with open(tmp, "wb") as f:
            f.write(content)
        os.replace(tmp, target)
        return thumb_rel_path(record_id)
    except Exception as e:
        logger.warning(
            f"封面缓存失败 (record={record_id}, url={url}): {type(e).__name__}: {e}"
        )
        _remove_quietly(tmp)
        return None


def delete_thumb(record_id: int, thumb_path: str | None = None) -> bool:
    """删除某条记录对应的本地封面文件。返回是否真的删掉了文件。"""
    removed = False
    for path in _candidate_paths(record_id, thumb_path):
        if _remove_quietly(path):
            removed = True
    return removed


def clear_thumbs() -> int:
    """删除缓存目录下的全部封面文件，返回删除数量。"""
    directory = thumb_dir()
    if not os.path.isdir(directory):
        return 0

    count = 0
    for name in os.listdir(directory):
        if _remove_quietly(os.path.join(directory, name)):
            count += 1
    return count


def guess_media_type(path: str) -> str:
    """按文件头猜图片类型（封面实际可能是 png / webp，却统一存成 .jpg）。"""
    try:
        with open(path, "rb") as f:
            head = f.read(16)
    except OSError:
        return "image/jpeg"

    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def _candidate_paths(record_id: int, thumb_path: str | None) -> list[str]:
    """待删除的候选路径：按记录 id 推导的路径 + 库里存的相对路径。"""
    paths = [thumb_abs_path(record_id)]
    if not thumb_path:
        return paths

    candidate = os.path.normpath(os.path.join(config.HISTORY_DIR, thumb_path))
    root = os.path.normpath(thumb_dir())
    try:
        inside = os.path.commonpath([candidate, root]) == root
    except ValueError:  # 不同盘符
        inside = False
    # 只删缓存目录内的文件，防止库里存的路径被写坏后误删别处
    if inside:
        paths.append(candidate)
    return paths


def _remove_quietly(path: str) -> bool:
    try:
        if os.path.isfile(path):
            os.remove(path)
            return True
    except OSError as e:
        logger.warning(f"删除封面文件失败 ({path}): {e}")
    return False
