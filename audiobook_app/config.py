import os
from pathlib import Path


class Config:
    BASE_DIR = Path(__file__).resolve().parent
    OUTPUT_FOLDER = BASE_DIR / "outputs"
    PDF_UPLOADS_FOLDER = BASE_DIR / "pdf_uploads"
    STATIC_FOLDER = BASE_DIR / "static"

    # Ensure folders exist
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
    PDF_UPLOADS_FOLDER.mkdir(parents=True, exist_ok=True)

    MAX_FILE_SIZE_MB = 50
    MAX_CONTENT_LENGTH = MAX_FILE_SIZE_MB * 1024 * 1024

    FILE_EXPIRY_SECONDS = 60 * 60  # 1 hour
    CLEANUP_INTERVAL_SECONDS = 10 * 60  # 10 minutes

    TTS_CHUNK_WORDS = 500
    TTS_MAX_CONCURRENT_WORKERS = 6
    TTS_PREVIEW_CHUNKS = 1
    TTS_CHUNK_TIMEOUT_SECONDS = 30
    TTS_MAX_RETRIES = 2
    SPELL_CHECK_ENABLED = True
    SPELL_CHECK_TRANSFORMER = False  # Enable transformer-based correction for gibberish
    VIDEO_FPS = 6
    EXTRACTION_CACHE_TTL_SECONDS = 30 * 60  # 30 minutes

    CAPTION_MIN_WORDS = 8
    CAPTION_MAX_WORDS = 10
    CAPTION_MAX_GAP_MS = 900
    VOICE_PREVIEW_TEXT = (
        "Hello, this is a voice preview from Bookdio. "
        "Use this sample to compare narration style and clarity."
    )
    VOICE_PREVIEW_MAX_TEXT_CHARS = 300

    # Video Settings
    VIDEO_RES = (1920, 1080)
    VIDEO_BG_COLOR = (0, 0, 0)
    VIDEO_FONT = "Arial"
    VIDEO_FONT_SIZE = 80
    VIDEO_ACTIVE_COLOR = "#FFD700"
    VIDEO_TEXT_COLOR = "white"
    VIDEO_RENDER_VERSION = "preview-v14"

    AVAILABLE_FONTS = [
        {"label": "Inter", "value": "'Inter', sans-serif", "file": "inter.ttf", "fallback": "arial.ttf"},
        {"label": "Arial", "value": "Arial, sans-serif", "file": "arial.ttf"},
        {"label": "Georgia", "value": "Georgia, serif", "file": "georgia.ttf", "fallback": "times.ttf"},
        {"label": "Courier New", "value": "'Courier New', monospace", "file": "cour.ttf"},
        {"label": "Verdana", "value": "Verdana, sans-serif", "file": "verdana.ttf", "fallback": "arial.ttf"},
        {"label": "Trebuchet MS", "value": "'Trebuchet MS', sans-serif", "file": "trebuc.ttf", "fallback": "arial.ttf"},
        {"label": "Comic Sans MS", "value": "'Comic Sans MS', cursive", "file": "comic.ttf", "fallback": "arial.ttf"},
        {"label": "Impact", "value": "Impact, sans-serif", "file": "impact.ttf", "fallback": "arial.ttf"},
    ]

    AVAILABLE_URDU_FONTS = [
        {"label": "Noto Nastaliq Urdu", "value": "'Noto Nastaliq Urdu', serif", "file": "noto-nastaliq-urdu.otf", "fallback": "arial.ttf"},
    ]

    URDU_VOICES = [
        "ur-PK-AsadNeural",
        "ur-PK-UzmaNeural",
    ]

    PORT = 5000
    DEBUG = True
