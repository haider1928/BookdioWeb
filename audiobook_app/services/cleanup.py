import os
import time
import threading
from pathlib import Path


def cleanup_old_outputs(folder: Path, expiry_seconds: int):
    now = time.time()
    if not folder.exists():
        return

    for file_path in folder.iterdir():
        if file_path.is_file() and file_path.suffix in [".mp3", ".vtt", ".mp4"]:
            file_age = now - file_path.stat().st_mtime
            if file_age > expiry_seconds:
                try:
                    file_path.unlink()
                except Exception as e:
                    print(f"Error deleting {file_path}: {e}")


def start_cleanup_thread(folder: Path, expiry_seconds: int, interval_seconds: int):
    def run_cleanup():
        while True:
            cleanup_old_outputs(folder, expiry_seconds)
            time.sleep(interval_seconds)

    thread = threading.Thread(target=run_cleanup, daemon=True)
    thread.start()
