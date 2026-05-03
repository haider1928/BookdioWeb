import os
from flask import Blueprint, send_file
from routes import error_response, success_response
from services.job_manager import get_full_job_data

subtitles_bp = Blueprint("subtitles", __name__)


@subtitles_bp.route("/subtitles/<job_id>", methods=["GET"])
def subtitles(job_id):
    job = get_full_job_data(job_id)
    if not job:
        return error_response("Job not found", 404)
    
    if not job["vtt_ready"]:
        return error_response("VTT not ready yet", 202)
        
    vtt_path = job["vtt_path"]
    if not vtt_path or not os.path.exists(vtt_path):
        return error_response("VTT file not found", 404)
        
    response = send_file(
        vtt_path,
        mimetype="text/vtt",
        as_attachment=False
    )
    # Add CORS header as requested
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


@subtitles_bp.route("/subtitles/<job_id>/words", methods=["GET"])
def subtitles_words(job_id):
    job = get_full_job_data(job_id)
    if not job:
        return error_response("Job not found", 404)
    if not job["vtt_ready"]:
        return error_response("Word VTT not ready yet", 202)

    word_vtt_path = job["word_vtt_path"]
    if not word_vtt_path or not os.path.exists(word_vtt_path):
        return error_response("Word VTT file not found", 404)

    response = send_file(word_vtt_path, mimetype="text/vtt", as_attachment=False)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


@subtitles_bp.route("/subtitles/<job_id>/captions", methods=["GET"])
def captions(job_id):
    job = get_full_job_data(job_id)
    if not job:
        return error_response("Job not found", 404)
    if not job["captions_ready"]:
        return error_response("Captions not ready yet", 202)

    return success_response({"captions": job["captions"]})
