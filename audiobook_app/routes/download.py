from time import sleep

from flask import Blueprint, Response, stream_with_context

from config import Config
from routes import error_response
from services.job_manager import get_job, get_job_output_path, is_job_finished

download_bp = Blueprint("download", __name__)


@download_bp.get("/download/<job_id>")
def download_file(job_id):
    job = get_job(job_id)
    file_path = get_job_output_path(job_id)
    if not job or not file_path:
        return error_response("Job not found.", 404)

    if not file_path.exists():
        return error_response("Audio file is not ready yet.", 425)

    def generate():
        position = 0
        while True:
            if file_path.exists():
                with file_path.open("rb") as audio_file:
                    audio_file.seek(position)
                    while True:
                        data = audio_file.read(8192)
                        if not data:
                            break
                        position += len(data)
                        yield data

            if is_job_finished(job_id):
                break

            sleep(Config.STREAM_SLEEP_SECONDS)

    headers = {
        "Content-Type": "audio/mpeg",
        "Content-Disposition": 'attachment; filename="audiobook.mp3"',
        "Transfer-Encoding": "chunked",
        "Cache-Control": "no-store",
    }
    return Response(stream_with_context(generate()), headers=headers)
