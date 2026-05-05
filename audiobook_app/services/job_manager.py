from __future__ import annotations

import threading
import time
from pathlib import Path
from uuid import uuid4

from config import Config
from services.captioning import build_caption_lines, write_line_vtt, write_word_vtt
from services.tts_engine import run_tts_job

# In-memory job store
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def create_job(text_chunks: list[str], voice: str, speed: str) -> dict:
    job_id = str(uuid4().hex)
    mp3_path = Config.OUTPUT_FOLDER / f"{job_id}.mp3"
    word_vtt_path = Config.OUTPUT_FOLDER / f"{job_id}.words.vtt"
    line_vtt_path = Config.OUTPUT_FOLDER / f"{job_id}.vtt"

    job = {
        "job_id": job_id,
        "status": "pending",
        "chunks_done": 0,
        "chunks_total": len(text_chunks),
        "preview_ready": False,
        "vtt_ready": False,
        "captions_ready": False,
        "vtt_entries": [],  # list of {word, startMs, endMs}
        "captions": [],  # list of {index, text, startMs, endMs, words}
        "word_vtt_path": str(word_vtt_path),
        "vtt_path": str(line_vtt_path),
        "mp3_path": str(mp3_path),
        "time_offset_ms": 0,
        "video_status": "idle",
        "video_progress": 0,
        "video_render_version": Config.VIDEO_RENDER_VERSION,
        "video_error": None,
        "video_style": {},
        "error": None,
        "created_at": time.time(),
        "started_at": time.time(),
        "avg_chunk_time_ms": 0,
    }

    with _jobs_lock:
        _jobs[job_id] = job

    # Start background processing
    thread = threading.Thread(
        target=_process_job,
        args=(job_id, text_chunks, voice, speed),
        daemon=True
    )
    thread.start()

    return _public_job_info(job)


def get_job(job_id: str) -> dict | None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return None
        return _public_job_info(job)


def get_full_job_data(job_id: str) -> dict | None:
    with _jobs_lock:
        return _jobs.get(job_id)


def update_job(job_id: str, **kwargs):
    with _jobs_lock:
        if job_id in _jobs:
            job = _jobs[job_id]
            job.update(kwargs)
            # Calculate avg chunk time and ETA
            if "chunks_done" in kwargs and job["chunks_total"] > 0:
                elapsed = time.time() - job.get("started_at", time.time())
                done = job["chunks_done"]
                if done > 0:
                    job["avg_chunk_time_ms"] = (elapsed / done) * 1000


def _public_job_info(job: dict) -> dict:
    elapsed = time.time() - job.get("started_at", time.time())
    remaining = job["chunks_total"] - job["chunks_done"]
    eta_seconds = int((job["avg_chunk_time_ms"] / 1000) * remaining) if job["chunks_done"] > 0 else 0

    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "chunks_done": job["chunks_done"],
        "chunks_total": job["chunks_total"],
        "preview_ready": job["preview_ready"],
        "vtt_ready": job["vtt_ready"],
        "captions_ready": job["captions_ready"],
        "video_status": job.get("video_status", "idle"),
        "video_progress": job.get("video_progress", 0),
        "video_error": job.get("video_error"),
        "error": job["error"],
        "eta_seconds": eta_seconds,
        "elapsed_seconds": int(elapsed),
    }


def _process_job(job_id: str, text_chunks: list[str], voice: str, speed: str):
    try:
        update_job(job_id, status="processing")
        
        # Run the actual TTS engine
        run_tts_job(job_id, text_chunks, voice, speed, update_job, get_full_job_data)
        
        update_job(job_id, status="done")
    except Exception as e:
        update_job(job_id, status="error", error=str(e))


def append_to_vtt(job_id: str, entries: list[dict]):
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id]["vtt_entries"].extend(entries)


def rebuild_captions(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return
        lines = build_caption_lines(
            job["vtt_entries"],
            Config.CAPTION_MIN_WORDS,
            Config.CAPTION_MAX_WORDS,
            Config.CAPTION_MAX_GAP_MS,
        )
        job["captions"] = lines
        job["captions_ready"] = len(lines) > 0


def write_vtt_file(job_id: str):
    job = get_full_job_data(job_id)
    if not job:
        return

    word_vtt_path = Path(job["word_vtt_path"])
    line_vtt_path = Path(job["vtt_path"])
    entries = job["vtt_entries"]
    lines = job["captions"]

    write_word_vtt(word_vtt_path, entries)
    write_line_vtt(line_vtt_path, lines)
    update_job(job_id, vtt_ready=True, captions_ready=len(lines) > 0)
