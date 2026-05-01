from flask import Blueprint, request
from werkzeug.utils import secure_filename

from routes import error_response, success_response
from services.pdf_extractor import extract_pdf_text

upload_bp = Blueprint("upload", __name__)


@upload_bp.post("/upload")
def upload_pdf():
    if "file" not in request.files:
        return error_response("No PDF file was uploaded.", 400)

    uploaded_file = request.files["file"]
    if not uploaded_file or not uploaded_file.filename:
        return error_response("No PDF file was selected.", 400)

    filename = secure_filename(uploaded_file.filename)
    if not filename.lower().endswith(".pdf"):
        return error_response("Only PDF files are supported.", 400)

    try:
        result = extract_pdf_text(uploaded_file.read())
    except ValueError as exc:
        return error_response(str(exc), 400)
    except Exception:
        return error_response("Failed to extract text from the PDF.", 500)

    return success_response(
        {
            "filename": filename,
            "page_count": result["page_count"],
            "text": result["text"],
        }
    )
