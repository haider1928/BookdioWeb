import threading
import time
from uuid import uuid4
from pathlib import Path

from services.pdf_extractor import extract_pdf_text

# In-memory store for extraction jobs
_extraction_jobs = {}
_extraction_lock = threading.Lock()

def create_extraction_job(pdf_path: Path, page_start: int | None = None, page_end: int | None = None) -> str:
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
        args=(job_id, pdf_path, page_start, page_end),
        daemon=True
    )
    thread.start()
    
    return job_id

def get_extraction_status(job_id: str) -> dict | None:
    with _extraction_lock:
        return _extraction_jobs.get(job_id)

def _run_extraction(job_id: str, pdf_path: Path, page_start: int | None, page_end: int | None):
    def progress_callback(done, total):
        with _extraction_lock:
            if job_id in _extraction_jobs:
                _extraction_jobs[job_id].update({
                    "status": "extracting",
                    "pages_done": done,
                    "pages_total": total
                })

    try:
        result = extract_pdf_text(
            pdf_path=pdf_path,
            page_start=page_start,
            page_end=page_end,
            progress_callback=progress_callback
        )
        
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
