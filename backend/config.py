import os
import shutil
import socket
import subprocess
import logging

# Load .env file
_env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_path):
    with open(_env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))

# uvicorn 热重载会多出一个 reloader 父进程，它持有监听 socket、子进程负责服务。
# 父进程一旦被杀（后台任务超时、进程被回收），子进程会变成持有 socket 的孤儿，
# 端口仍被占用但父进程已不在；再起一个实例时，Windows 的 SO_REUSEADDR 允许
# 同端口重复绑定，结果是两个服务同时监听、请求随机分流。
# 常驻服务请设 RELOAD=0，以单进程模式运行。
RELOAD = os.getenv("RELOAD", "1").strip().lower() not in ("0", "false", "no")


def _proxy_reachable(proxy: str) -> bool:
    """检查代理地址的端口是否真的可连接。"""
    if not proxy:
        return False
    try:
        from urllib.parse import urlparse
        parsed = urlparse(proxy if "://" in proxy else f"http://{proxy}")
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        with socket.create_connection((host, port), timeout=1.5):
            return True
    except Exception:
        return False


def _resolve_proxy() -> str:
    """读取 PROXY 配置；若代理未运行则回退为直连。

    yt-dlp 不读 Windows 系统代理，必须显式指定 PROXY 才能走代理。
    但 Clash Verge 未启动时，硬套一个不通的代理会让所有请求报
    WinError 10061（连国内平台也一起挂）。这里做一次端口探测，
    代理不可用就退回直连，保证国内平台始终可用。
    """
    proxy = os.getenv("PROXY", "").strip()
    if proxy and not _proxy_reachable(proxy):
        print(f"[config] 警告: 代理 {proxy} 不可用（端口未监听），已回退为直连连接")
        return ""
    return proxy


PROXY = _resolve_proxy()

DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "downloads")
SUBTITLE_DIR = os.path.join(os.path.dirname(__file__), "subtitles")
DB_PATH = os.path.join(os.path.dirname(__file__), "history.db")

# Auto-detect ffmpeg location
# 查找优先级: FFMPEG_PATH 环境变量 > PATH > 常见安装目录
# 注意: 必须返回绝对路径。yt-dlp 的 ffmpeg_location 只做 os.path.exists 判断，
# 传裸命令名（如 "ffmpeg"）即使在 PATH 上也会被判为"不存在"，导致音视频合并被跳过。
def _normalize_ffmpeg(value: str) -> str:
    """接受可执行文件路径或目录，返回可执行文件路径。"""
    if not value:
        return ""
    if os.path.isdir(value):
        for name in ("ffmpeg.exe", "ffmpeg"):
            candidate = os.path.join(value, name)
            if os.path.isfile(candidate):
                return candidate
        return ""
    return value


def _search_dirs() -> list:
    """常见 ffmpeg 安装目录，winget 目录排在最前（按版本倒序）。"""
    localappdata = os.environ.get("LOCALAPPDATA", "")
    programfiles = os.environ.get("ProgramFiles", r"C:\Program Files")
    programfiles_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    userprofile = os.environ.get("USERPROFILE", "")

    candidates = []

    # winget 安装包目录（可能存在多个版本）
    winget_dir = os.path.join(localappdata, "Microsoft", "WinGet", "Packages")
    if os.path.isdir(winget_dir):
        for pkg in sorted(os.listdir(winget_dir), reverse=True):
            if "ffmpeg" in pkg.lower():
                candidates.append(os.path.join(winget_dir, pkg))

    candidates += [
        os.path.join(programfiles, "ffmpeg", "bin"),
        os.path.join(programfiles_x86, "ffmpeg", "bin"),
        os.path.join(programfiles, "FFmpeg", "bin"),
        r"C:\ffmpeg\bin",
        os.path.join(programfiles, "chocolatey", "bin"),
        os.path.join(userprofile, "scoop", "shims"),
    ]
    return candidates


def _find_ffmpeg() -> str:
    # 1) 显式指定（环境变量或 backend/.env 里的 FFMPEG_PATH）
    override = _normalize_ffmpeg(os.getenv("FFMPEG_PATH", "").strip())
    if override:
        return override

    # 2) PATH 上直接可调用（返回绝对路径）
    on_path = shutil.which("ffmpeg")
    if on_path:
        return on_path

    # 3) 常见安装目录
    for base in _search_dirs():
        if not os.path.isdir(base):
            continue
        for root, _dirs, files in os.walk(base):
            if "ffmpeg.exe" in files:
                return os.path.join(root, "ffmpeg.exe")

    return "ffmpeg"


def _find_ffprobe() -> str:
    """ffprobe 通常与 ffmpeg 同目录；不要用字符串替换推导路径。"""
    override = os.getenv("FFPROBE_PATH", "").strip()
    if override:
        return override

    if FFMPEG_PATH.lower().endswith(".exe"):
        candidate = os.path.join(os.path.dirname(FFMPEG_PATH), "ffprobe.exe")
        if os.path.isfile(candidate):
            return candidate

    on_path = shutil.which("ffprobe")
    if on_path:
        return on_path

    return "ffprobe"


FFMPEG_PATH = _find_ffmpeg()
FFPROBE_PATH = _find_ffprobe()


MAX_CONCURRENT_DOWNLOADS = 5
FILE_CLEANUP_SECONDS = 3600
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB

# yt-dlp 解析 YouTube 依赖 JS 运行时（无 JS 的提取路径已被 yt-dlp 弃用，
# 会导致部分清晰度缺失甚至提取失败）。本机已装 Node，直接复用；
# 找不到 node 时不设置该选项，yt-dlp 会退回默认的 deno 探测。
JS_RUNTIMES = {"node": {}} if shutil.which("node") else {}

# YouTube 的 n 签名需要挑战求解脚本（EJS）。不开启时 yt-dlp 会提示
# "Signature solving failed: Some formats may be missing"，导致部分清晰度缺失。
# 官方推荐开启 ejs:github，脚本会在首次使用时自动下载并缓存。
YT_REMOTE_COMPONENTS = ["ejs:github"]

# yt-dlp 超时与重试。默认 socket 超时只有 20s，代理节点偏慢时单次请求
# 容易被判超时直接失败。放宽超时并保留重试，让"慢"变成"等"而不是"失败"。
YT_SOCKET_TIMEOUT = 30

# 重试次数。yt-dlp 默认 retries=10；之前调成 3 会导致代理链路出现瞬时
# SSL 抖动（UNEXPECTED_EOF_WHILE_READING）时过早放弃，整个下载前功尽弃。
YT_RETRIES = int(os.getenv("YT_RETRIES", "10"))
YT_FRAGMENT_RETRIES = int(os.getenv("YT_FRAGMENT_RETRIES", "10"))

# 断点续传：下载中断后重试会从 .part 已有字节继续，而不是从头再来。
# （注意：每次下载任务的 task_id 不同，所以是同一次任务内的重试受益；
#   用户手动重发任务会生成新文件名，无法续传旧分片。）
YT_CONTINUEDL = os.getenv("YT_CONTINUEDL", "1").strip().lower() not in ("0", "false", "no")

# 重试退避上限（秒）。指数退避，给不稳定的代理链路留出恢复时间。
YT_RETRY_SLEEP_MAX = int(os.getenv("YT_RETRY_SLEEP_MAX", "30"))

# 下载彻底失败后，用「单文件最佳格式」再兜底一次。
# 合并流（video+audio）要下两个文件，任一失败就整条失败；best 单流有时走
# 的是另一条 CDN 路径，能救回来。
YT_DOWNLOAD_FALLBACK = os.getenv("YT_DOWNLOAD_FALLBACK", "1").strip().lower() not in ("0", "false", "no")

# 解析结果缓存。yt-dlp 解析 YouTube 需多轮网络请求，节点偏慢时单次要
# 10~25 秒；同一 URL 反复解析时命中缓存可秒回。
# 视频元数据短时间内不会变化，默认缓存 30 分钟；设 PARSE_CACHE_TTL=0 可关闭。
PARSE_CACHE_TTL = int(os.getenv("PARSE_CACHE_TTL", "1800"))
PARSE_CACHE_MAX = int(os.getenv("PARSE_CACHE_MAX", "200"))

CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]

# AI Summarization
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# Bilibili (optional, for videos that require login to access subtitles)
BILIBILI_SESSDATA = os.getenv("BILIBILI_SESSDATA", "")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(SUBTITLE_DIR, exist_ok=True)

# ============ 应用日志 ============
# uvicorn 热重载会重建子进程，stdout/stderr 句柄随之丢失，日志只留下启动那几行。
# 额外落一份到文件，排查下载/解析异常时才有据可查。
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)


def _setup_file_logging() -> None:
    log_file = os.path.join(LOG_DIR, "app.log")
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not any(
        isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", "") == os.path.abspath(log_file)
        for h in root.handlers
    ):
        root.addHandler(handler)


_setup_file_logging()
