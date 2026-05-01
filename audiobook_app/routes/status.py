from flask import Blueprint, url_for

from routes import error_response, success_response
from services.job_manager import get_job

status_bp = Blueprint("status", __name__)


@status_bp.get("/status/<job_id>")
def get_status(job_id):
    job = get_job(job_id)
    if not job:
        return error_response("Job not found.", 404)

    return success_response(
        {
            "job_id": job["job_id"],
            "status": job["status"],
            "chunks_done": job["chunks_done"],
            "chunks_total": job["chunks_total"],
            "preview_ready": job["preview_ready"],
            "error": job["error"],
            "preview_url": url_for("preview.preview_audio", job_id=job["job_id"]),
            "download_url": url_for("download.download_file", job_id=job["job_id"]),
        }
    )
