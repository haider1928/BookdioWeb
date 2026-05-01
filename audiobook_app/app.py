from flask import Flask
from flask_cors import CORS

from config import Config
from routes import register_blueprints
from services.cleanup import cleanup_old_outputs, start_cleanup_thread


def create_app() -> Flask:
    Config.OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

    app = Flask(
        __name__,
        static_folder=str(Config.STATIC_FOLDER),
    )
    app.config["MAX_CONTENT_LENGTH"] = Config.MAX_CONTENT_LENGTH

    CORS(app)
    register_blueprints(app)
    cleanup_old_outputs(Config.OUTPUT_FOLDER, Config.FILE_EXPIRY_SECONDS)
    start_cleanup_thread(
        Config.OUTPUT_FOLDER,
        Config.FILE_EXPIRY_SECONDS,
        Config.CLEANUP_INTERVAL_SECONDS,
    )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(port=Config.PORT, debug=Config.DEBUG, use_reloader=False)
