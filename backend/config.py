import os
import shutil
import subprocess

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

PROXY = os.getenv("PROXY", "")

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
