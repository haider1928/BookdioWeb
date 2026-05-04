from flask import Blueprint
from routes import success_response, error_response
from services.job_manager import get_job

status_bp = Blueprint("status", __name__)


@status_bp.route("/status/<job_id>", methods=["GET"])
def status(job_id):
    job_info = get_job(job_id)
    if not job_info:
        return error_response("Job not found", 404)
    
    return success_response(job_info)
