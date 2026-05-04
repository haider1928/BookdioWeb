import os
from flask import Blueprint, request, Response, send_file
from routes import error_response
from services.job_manager import get_full_job_data

preview_bp = Blueprint("preview", __name__)


@preview_bp.route("/preview/<job_id>", methods=["GET"])
def preview(job_id):
    job = get_full_job_data(job_id)
    if not job:
        return error_response("Job not found", 404)
    
    mp3_path = job["mp3_path"]
    if not os.path.exists(mp3_path):
        return error_response("MP3 not ready", 425)

    # Support range requests for partial playback
    # Flask's send_file handles range requests automatically if configured
    return send_file(
        mp3_path,
        mimetype="audio/mpeg",
        as_attachment=False,
        conditional=True
    )
