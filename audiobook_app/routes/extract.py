from flask import Blueprint, request
from config import Config
from routes import success_response, error_response
from services.extraction_manager import create_extraction_job, get_extraction_status

extract_bp = Blueprint("extract", __name__)

@extract_bp.route("/extract", methods=["POST"])
def start_extraction():
    data = request.get_json() or {}
    upload_id = data.get("upload_id")

    if not upload_id:
        return error_response("Missing upload_id")

    file_path = Config.PDF_UPLOADS_FOLDER / upload_id
    if not file_path.exists():
        return error_response("File not found on server")

    page_start = data.get("page_start")
    page_end = data.get("page_end")
    use_spell_check = data.get("use_spell_check", True)
    if not isinstance(use_spell_check, bool):
        use_spell_check = str(use_spell_check).lower() == "true"

    translate_to_urdu = data.get("translate_to_urdu", False)
    if not isinstance(translate_to_urdu, bool):
        translate_to_urdu = str(translate_to_urdu).lower() == "true"

    try:
        if page_start is not None:
            page_start = int(page_start)
        if page_end is not None:
            page_end = int(page_end)
    except ValueError:
        return error_response("Invalid page range")

    print(f"[EXTRACT] translate_to_urdu: {translate_to_urdu}")
    job_id = create_extraction_job(file_path, page_start, page_end, use_spell_check=use_spell_check, translate_to_urdu=translate_to_urdu)
    return success_response({"job_id": job_id})

@extract_bp.route("/extract/status/<job_id>", methods=["GET"])
def extraction_status(job_id):
    status = get_extraction_status(job_id)
    if not status:
        return error_response("Extraction job not found", 404)
        
    return success_response(status)
