import os
from uuid import uuid4
from flask import Blueprint, request
from config import Config
from routes import success_response, error_response

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
            # Generate a unique ID for the upload
            upload_id = f"{uuid4().hex}.pdf"
            save_path = Config.PDF_UPLOADS_FOLDER / upload_id
            
            # Save the file with buffered write to avoid memory issues
            with open(save_path, "wb") as f:
                while True:
                    chunk = file.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
            
            return success_response({"upload_id": upload_id})
        except Exception as e:
            return error_response(f"Upload failed: {str(e)}")
    
    return error_response("Invalid file type. Please upload a PDF.")
