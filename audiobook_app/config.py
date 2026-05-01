from pathlib import Path


class Config:
    BASE_DIR = Path(__file__).resolve().parent
    OUTPUT_FOLDER = BASE_DIR / "outputs"
    STATIC_FOLDER = BASE_DIR / "static"

    MAX_FILE_SIZE_MB = 50
    MAX_CONTENT_LENGTH = MAX_FILE_SIZE_MB * 1024 * 1024

    FILE_EXPIRY_SECONDS = 60 * 60
    CLEANUP_INTERVAL_SECONDS = 5 * 60
    TTS_CHUNK_WORDS = 500
    TTS_PREVIEW_CHUNKS = 2
    TTS_CHUNK_TIMEOUT_SECONDS = 30
    TTS_MAX_RETRIES = 2
    STREAM_SLEEP_SECONDS = 0.5

    PORT = 5000
    DEBUG = True
