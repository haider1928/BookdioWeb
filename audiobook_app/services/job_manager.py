from __future__ import annotations

from pathlib import Path
from threading import Lock, Thread
from time import time
from uuid import uuid4

from config import Config
from services.tts_engine import format_rate, save_chunk_with_retries_sync, split_text_into_chunks

_jobs: dict[str, dict] = {}
_jobs_lock = Lock()


def create_job(text: str, voice: str, speed) -> dict:
    chunks = split_text_into_chunks(text, Config.TTS_CHUNK_WORDS)
    if not chunks:
        raise ValueError("Text content is required.")

    job_id = uuid4().hex
    rate = format_rate(speed)
    output_path = Config.OUTPUT_FOLDER / f"{job_id}.mp3"
    output_path.touch()

    job = {
        "job_id": job_id,
        "status": "queued",
        "voice": voice,
        "speed": rate,
        "chunks": chunks,
        "chunks_done": 0,
        "chunks_total": len(chunks),
        "preview_ready": False,
        "error": "",
        "output_path": output_path,
        "created_at": time(),
        "updated_at": time(),
    }

    with _jobs_lock:
        _jobs[job_id] = job

    worker = Thread(target=_process_job, args=(job_id,), name=f"audiobook-job-{job_id}", daemon=True)
    worker.start()

    return get_job(job_id)


def get_job(job_id: str) -> dict | None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return None
        return _public_job(job)


def get_job_output_path(job_id: str) -> Path | None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return None
        return job["output_path"]


def is_job_finished(job_id: str) -> bool:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return True
        return job["status"] in {"complete", "error"}


def mark_job_error(job_id: str, message: str) -> None:
    _update_job(job_id, status="error", error=message)


def _public_job(job: dict) -> dict:
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "chunks_done": job["chunks_done"],
        "chunks_total": job["chunks_total"],
        "preview_ready": job["preview_ready"],
        "error": job["error"],
        "voice": job["voice"],
        "speed": job["speed"],
    }


def _update_job(job_id: str, **changes) -> None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return
        job.update(changes)
        job["updated_at"] = time()


def _append_file(source_path: Path, destination_path: Path) -> None:
    with source_path.open("rb") as source, destination_path.open("ab") as destination:
        while True:
            data = source.read(1024 * 128)
            if not data:
                break
            destination.write(data)
        destination.flush()


def _process_job(job_id: str) -> None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return
        chunks = list(job["chunks"])
        voice = job["voice"]
        rate = job["speed"]
        output_path = job["output_path"]

    _update_job(job_id, status="processing")

    try:
        for index, chunk in enumerate(chunks, start=1):
            temp_path = Config.OUTPUT_FOLDER / f"{job_id}.{index}.part.mp3"
            save_chunk_with_retries_sync(
                chunk,
                voice,
                rate,
                temp_path,
                timeout_seconds=Config.TTS_CHUNK_TIMEOUT_SECONDS,
                max_retries=Config.TTS_MAX_RETRIES,
            )
            _append_file(temp_path, output_path)
            temp_path.unlink(missing_ok=True)

            preview_ready = index >= min(Config.TTS_PREVIEW_CHUNKS, len(chunks))
            _update_job(
                job_id,
                chunks_done=index,
                preview_ready=preview_ready,
                status="processing",
            )

        _update_job(job_id, status="complete", preview_ready=True, chunks_done=len(chunks))
    except Exception:
        mark_job_error(job_id, "EdgeTTS connection failed. Check internet connection or try again.")
