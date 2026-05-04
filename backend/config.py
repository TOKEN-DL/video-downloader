import os
import subprocess

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))

PROXY = os.getenv("PROXY", "")

DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "downloads")
SUBTITLE_DIR = os.path.join(os.path.dirname(__file__), "subtitles")
DB_PATH = os.path.join(os.path.dirname(__file__), "history.db")

# Auto-detect ffmpeg location
def _find_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return "ffmpeg"
    except Exception:
        winget_path = os.path.join(
            os.environ.get("LOCALAPPDATA", ""),
            "Microsoft", "WinGet", "Packages",
        )
        for pkg in os.listdir(winget_path) if os.path.isdir(winget_path) else []:
            if "FFmpeg" in pkg:
                candidate = os.path.join(winget_path, pkg)
                for root, dirs, files in os.walk(candidate):
                    if "ffmpeg.exe" in files:
                        return os.path.join(root, "ffmpeg.exe")
    return "ffmpeg"

FFMPEG_PATH = _find_ffmpeg()

MAX_CONCURRENT_DOWNLOADS = 5
FILE_CLEANUP_SECONDS = 3600
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB

CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(SUBTITLE_DIR, exist_ok=True)
