import hashlib
import threading
import time
from uuid import uuid4
from pathlib import Path

from config import Config
from services.pdf_extractor import extract_pdf_text

# In-memory store for extraction jobs
_extraction_jobs = {}
_extraction_lock = threading.Lock()

# Extraction cache by PDF hash
_extraction_cache: dict[str, dict] = {}


def _get_pdf_hash(pdf_path: Path) -> str:
    """Compute SHA-256 hash of a PDF file."""
    h = hashlib.sha256()
    with open(pdf_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _clean_expired_cache():
    """Remove expired cache entries."""
    now = time.time()
    expired = [
        k for k, v in _extraction_cache.items()
        if now - v["timestamp"] > Config.EXTRACTION_CACHE_TTL_SECONDS
    ]
    for k in expired:
        del _extraction_cache[k]


def create_extraction_job(pdf_path: Path, page_start: int | None = None, page_end: int | None = None, use_spell_check: bool = True, translate_to_urdu: bool = False) -> str:
    # Check cache first
    cache_key = f"{_get_pdf_hash(pdf_path)}:{page_start}:{page_end}:{use_spell_check}:{translate_to_urdu}"
    _clean_expired_cache()
    cached = _extraction_cache.get(cache_key)
    if cached:
        print(f"[EXTRACTION] Cache hit for {pdf_path.name} ({cache_key[:16]}...)")
        job_id = str(uuid4().hex)
        job = {
            "job_id": job_id,
            "status": "done",
            "pages_done": 1,
            "pages_total": 1,
            "result": cached["result"],
            "error": None,
            "created_at": time.time()
        }
        with _extraction_lock:
            _extraction_jobs[job_id] = job
        return job_id

    job_id = str(uuid4().hex)

    job = {
        "job_id": job_id,
        "status": "pending",
        "pages_done": 0,
        "pages_total": 0,
        "result": None,
        "error": None,
        "created_at": time.time()
    }

    with _extraction_lock:
        _extraction_jobs[job_id] = job

    # Start background thread
    thread = threading.Thread(
        target=_run_extraction,
        args=(job_id, pdf_path, page_start, page_end, use_spell_check, translate_to_urdu),
        daemon=True
    )
    thread.start()

    return job_id

def get_extraction_status(job_id: str) -> dict | None:
    with _extraction_lock:
        return _extraction_jobs.get(job_id)

def _run_extraction(job_id: str, pdf_path: Path, page_start: int | None, page_end: int | None, use_spell_check: bool = True, translate_to_urdu: bool = False):
    def progress_callback(done, total):
        with _extraction_lock:
            if job_id in _extraction_jobs:
                _extraction_jobs[job_id].update({
                    "status": "extracting",
                    "pages_done": done,
                    "pages_total": total
                })

    def spell_progress_callback(done, total):
        with _extraction_lock:
            if job_id in _extraction_jobs:
                _extraction_jobs[job_id].update({
                    "status": "spellchecking",
                    "spell_done": done,
                    "spell_total": total
                })
                print(f"[EXTRACTION] Spell check: {done}/{total} sentences")

    try:
        print(f"[EXTRACTION] Starting extraction: {pdf_path.name}")
        result = extract_pdf_text(
            pdf_path=pdf_path,
            page_start=page_start,
            page_end=page_end,
            progress_callback=progress_callback,
            spell_progress_callback=spell_progress_callback,
            use_spell_check=use_spell_check,
            translate_to_urdu=translate_to_urdu
        )

        # Store in cache
        cache_key = f"{_get_pdf_hash(pdf_path)}:{page_start}:{page_end}:{use_spell_check}:{translate_to_urdu}"
        _extraction_cache[cache_key] = {"result": result, "timestamp": time.time()}
        print(f"[EXTRACTION] Cached result for {pdf_path.name}")

        with _extraction_lock:
            if job_id in _extraction_jobs:
                _extraction_jobs[job_id].update({
                    "status": "done",
                    "result": result
                })
    except Exception as e:
        with _extraction_lock:
            if job_id in _extraction_jobs:
                _extraction_jobs[job_id].update({
                    "status": "error",
                    "error": str(e)
                })
