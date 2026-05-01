from flask import Blueprint, send_file

from routes import error_response
from services.job_manager import get_job, get_job_output_path

preview_bp = Blueprint("preview", __name__)


@preview_bp.get("/preview/<job_id>")
def preview_audio(job_id):
    job = get_job(job_id)
    file_path = get_job_output_path(job_id)
    if not job or not file_path:
        return error_response("Job not found.", 404)

    if not job["preview_ready"] or not file_path.exists() or file_path.stat().st_size == 0:
        return error_response("Preview audio is not ready yet.", 425)

    response = send_file(
        file_path,
        mimetype="audio/mpeg",
        as_attachment=False,
        conditional=False,
        etag=False,
        max_age=0,
    )
    response.headers["Cache-Control"] = "no-store"
    return response
