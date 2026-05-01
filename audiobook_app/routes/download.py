from flask import Blueprint, send_from_directory
from werkzeug.utils import secure_filename

from config import Config
from routes import error_response

download_bp = Blueprint("download", __name__)


@download_bp.get("/download/<filename>")
def download_file(filename):
    safe_filename = secure_filename(filename)
    if not safe_filename or safe_filename != filename:
        return error_response("Invalid file name.", 400)

    file_path = Config.OUTPUT_FOLDER / safe_filename
    if not file_path.exists() or not file_path.is_file():
        return error_response("File not found.", 404)

    return send_from_directory(
        Config.OUTPUT_FOLDER,
        safe_filename,
        as_attachment=True,
        download_name=safe_filename,
        mimetype="audio/mpeg",
    )
