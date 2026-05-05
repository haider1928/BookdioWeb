# Windows Setup Instructions:
# Python 3.10+
# cd audiobook_app
# py -3.10 -m venv .venv
# .\.venv\Scripts\Activate.ps1
# pip install -r requirements.txt
# python app.py
# Open http://127.0.0.1:5000

from flask import Flask
from flask_cors import CORS

from config import Config
from routes import register_blueprints
from services.cleanup import start_cleanup_thread


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder=str(Config.STATIC_FOLDER),
        static_url_path="/static"
    )
    app.config["MAX_CONTENT_LENGTH"] = Config.MAX_CONTENT_LENGTH

    # Enable CORS globally
    CORS(app)

    # Register all routes
    register_blueprints(app)

    # Start background cleanup
    start_cleanup_thread(
        Config.OUTPUT_FOLDER,
        Config.FILE_EXPIRY_SECONDS,
        Config.CLEANUP_INTERVAL_SECONDS,
    )
    start_cleanup_thread(
        Config.PDF_UPLOADS_FOLDER,
        Config.FILE_EXPIRY_SECONDS,
        Config.CLEANUP_INTERVAL_SECONDS,
    )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=Config.PORT, debug=Config.DEBUG, use_reloader=True)
