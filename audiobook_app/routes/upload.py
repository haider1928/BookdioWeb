from flask import Blueprint, request
from routes import success_response, error_response
from services.pdf_extractor import extract_pdf_text

upload_bp = Blueprint("upload", __name__)


@upload_bp.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return error_response("No file part")
    
    file = request.files["file"]
    if file.filename == "":
        return error_response("No selected file")
    
    if file and file.filename.lower().endswith(".pdf"):
        try:
            pdf_bytes = file.read()
            result = extract_pdf_text(pdf_bytes)
            return success_response(result)
        except Exception as e:
            return error_response(str(e))
    
    return error_response("Invalid file type. Please upload a PDF.")
