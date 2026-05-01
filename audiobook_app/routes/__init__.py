from flask import Blueprint, jsonify, send_from_directory
from werkzeug.exceptions import HTTPException

from config import Config


def success_response(data: dict | list | None = None, status_code: int = 200):
    response = jsonify({"success": True, "data": {} if data is None else data})
    response.status_code = status_code
    return response


def error_response(message: str, status_code: int = 400):
    response = jsonify({"success": False, "error": message})
    response.status_code = status_code
    return response


frontend_bp = Blueprint("frontend", __name__)


@frontend_bp.get("/")
def index():
    return send_from_directory(Config.STATIC_FOLDER, "index.html")


def register_error_handlers(app):
    @app.errorhandler(413)
    def file_too_large(_):
        return error_response(f"PDF file must be {Config.MAX_FILE_SIZE_MB}MB or smaller.", 413)

    @app.errorhandler(HTTPException)
    def http_error(error):
        return error_response(error.description or "Request failed.", error.code or 500)

    @app.errorhandler(Exception)
    def unexpected_error(_):
        return error_response("An unexpected server error occurred.", 500)


def register_blueprints(app):
    from routes.convert import convert_bp
    from routes.download import download_bp
    from routes.preview import preview_bp
    from routes.status import status_bp
    from routes.upload import upload_bp
    from routes.voices import voices_bp

    app.register_blueprint(frontend_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(convert_bp)
    app.register_blueprint(status_bp)
    app.register_blueprint(preview_bp)
    app.register_blueprint(voices_bp)
    app.register_blueprint(download_bp)
    register_error_handlers(app)
