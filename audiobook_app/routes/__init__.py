from flask import Flask, jsonify, send_from_directory
from config import Config


def success_response(data=None, status_code=200):
    return jsonify({"success": True, "data": data or {}}), status_code


def error_response(message, status_code=400):
    return jsonify({"success": False, "error": message}), status_code


def register_blueprints(app: Flask):
    from routes.upload import upload_bp
    from routes.voices import voices_bp
    from routes.convert import convert_bp
    from routes.status import status_bp
    from routes.preview import preview_bp
    from routes.download import download_bp
    from routes.subtitles import subtitles_bp

    app.register_blueprint(upload_bp)
    app.register_blueprint(voices_bp)
    app.register_blueprint(convert_bp)
    app.register_blueprint(status_bp)
    app.register_blueprint(preview_bp)
    app.register_blueprint(download_bp)
    app.register_blueprint(subtitles_bp)

    @app.route("/")
    def index():
        return send_from_directory(Config.STATIC_FOLDER, "index.html")
