import os
from pathlib import Path


class Config:
    BASE_DIR = Path(__file__).resolve().parent
    OUTPUT_FOLDER = BASE_DIR / "outputs"
    STATIC_FOLDER = BASE_DIR / "static"

    # Ensure output folder exists
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

    MAX_FILE_SIZE_MB = 50
    MAX_CONTENT_LENGTH = MAX_FILE_SIZE_MB * 1024 * 1024

    FILE_EXPIRY_SECONDS = 60 * 60  # 1 hour
    CLEANUP_INTERVAL_SECONDS = 10 * 60  # 10 minutes

    TTS_CHUNK_WORDS = 500
    TTS_PREVIEW_CHUNKS = 1
    TTS_CHUNK_TIMEOUT_SECONDS = 30
    TTS_MAX_RETRIES = 2
    CAPTION_MIN_WORDS = 8
    CAPTION_MAX_WORDS = 10
    CAPTION_MAX_GAP_MS = 900

    # Video Settings
    VIDEO_RES = (1920, 1080)
    VIDEO_BG_COLOR = (0, 0, 0)
    VIDEO_FONT = "Arial"
    VIDEO_FONT_SIZE = 64
    VIDEO_ACTIVE_COLOR = "#FFD700"
    VIDEO_TEXT_COLOR = "white"

    PORT = 5000
    DEBUG = True
