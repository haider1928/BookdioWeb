from pathlib import Path
from threading import Event, Thread
from time import sleep, time

_cleanup_started = Event()
_cleanup_thread = None


def cleanup_old_outputs(output_folder: Path, expiry_seconds: int) -> int:
    output_folder.mkdir(parents=True, exist_ok=True)
    now = time()
    deleted = 0

    for file_path in output_folder.glob("*.mp3"):
        try:
            if file_path.is_file() and now - file_path.stat().st_mtime > expiry_seconds:
                file_path.unlink()
                deleted += 1
        except OSError:
            continue

    return deleted


def _cleanup_loop(output_folder: Path, expiry_seconds: int, interval_seconds: int) -> None:
    while True:
        cleanup_old_outputs(output_folder, expiry_seconds)
        sleep(interval_seconds)


def start_cleanup_thread(output_folder: Path, expiry_seconds: int, interval_seconds: int) -> None:
    global _cleanup_thread

    if _cleanup_started.is_set():
        return

    _cleanup_started.set()
    _cleanup_thread = Thread(
        target=_cleanup_loop,
        args=(output_folder, expiry_seconds, interval_seconds),
        name="audiobook-output-cleanup",
        daemon=True,
    )
    _cleanup_thread.start()
