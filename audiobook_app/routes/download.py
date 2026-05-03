import os
import threading
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from flask import Blueprint, send_file
from moviepy.editor import AudioFileClip, VideoClip

from config import Config
from routes import error_response, success_response
from services.job_manager import get_full_job_data, update_job

download_bp = Blueprint("download", __name__)
_video_locks: dict[str, threading.Lock] = {}


@download_bp.route("/download/<job_id>", methods=["GET"])
def download_audio(job_id):
    job = get_full_job_data(job_id)
    if not job:
        return error_response("Job not found", 404)

    mp3_path = job["mp3_path"]
    if not os.path.exists(mp3_path):
        return error_response("MP3 not ready", 425)

    return send_file(
        mp3_path,
        mimetype="audio/mpeg",
        as_attachment=True,
        download_name="audiobook.mp3",
    )


@download_bp.route("/download/<job_id>/video", methods=["GET"])
def request_video(job_id):
    job = get_full_job_data(job_id)
    if not job:
        return error_response("Job not found", 404)

    mp4_path = Config.OUTPUT_FOLDER / f"{job_id}.mp4"
    if mp4_path.exists():
        update_job(job_id, video_status="done", video_error=None)
        return success_response(
            {
                "video_status": "done",
                "download_url": f"/download/{job_id}/video/file",
            }
        )

    if job["status"] != "done":
        return error_response("Job must be complete before video generation", 425)

    current_status = job.get("video_status", "idle")
    if current_status == "generating":
        return success_response({"video_status": "generating"}, 202)

    update_job(job_id, video_status="generating", video_error=None)
    threading.Thread(target=_generate_video_safe, args=(job_id,), daemon=True).start()
    return success_response({"video_status": "generating"}, 202)


@download_bp.route("/download/<job_id>/video/status", methods=["GET"])
def video_status(job_id):
    job = get_full_job_data(job_id)
    if not job:
        return error_response("Job not found", 404)

    status = job.get("video_status", "idle")
    response = {"video_status": status, "video_error": job.get("video_error")}
    if status == "done":
        response["download_url"] = f"/download/{job_id}/video/file"
    return success_response(response)


@download_bp.route("/download/<job_id>/video/file", methods=["GET"])
def download_video_file(job_id):
    job = get_full_job_data(job_id)
    if not job:
        return error_response("Job not found", 404)

    mp4_path = Config.OUTPUT_FOLDER / f"{job_id}.mp4"
    if not mp4_path.exists():
        return error_response("Video not ready", 425)

    return send_file(
        str(mp4_path),
        mimetype="video/mp4",
        as_attachment=True,
        download_name="audiobook.mp4",
    )


def _generate_video_safe(job_id: str):
    lock = _video_locks.setdefault(job_id, threading.Lock())
    with lock:
        try:
            _generate_video(job_id)
            update_job(job_id, video_status="done", video_error=None)
        except Exception as exc:
            update_job(job_id, video_status="error", video_error=str(exc))


def _generate_video(job_id: str):
    job = get_full_job_data(job_id)
    if not job:
        raise ValueError("Job not found")

    captions = job.get("captions") or []
    if not captions:
        raise ValueError("No caption timeline available for rendering.")

    mp3_path = Path(job["mp3_path"])
    if not mp3_path.exists():
        raise ValueError("Audio file missing.")

    mp4_path = Config.OUTPUT_FOLDER / f"{job_id}.mp4"
    resolution = Config.VIDEO_RES
    background = Config.VIDEO_BG_COLOR

    title_font, body_font = _load_fonts()

    audio = AudioFileClip(str(mp3_path))

    def make_frame(t: float):
        current_ms = int(t * 1000)
        active_idx = _find_active_caption_index(captions, current_ms)
        prev_line = captions[active_idx - 1]["text"] if active_idx > 0 else ""
        active_line = captions[active_idx]["text"]
        next_line = captions[active_idx + 1]["text"] if active_idx < len(captions) - 1 else ""

        frame = Image.new("RGBA", resolution, color=(*background, 255))
        draw = ImageDraw.Draw(frame)

        center_y = resolution[1] // 2
        _draw_centered_text(draw, prev_line, center_y - 130, body_font, (135, 145, 165, 125), resolution[0])
        _draw_centered_text(draw, active_line, center_y, title_font, (255, 255, 255, 255), resolution[0], shadow=True)
        _draw_centered_text(draw, next_line, center_y + 120, body_font, (193, 203, 219, 188), resolution[0])

        return np.array(frame.convert("RGB"))

    video = VideoClip(make_frame, duration=audio.duration).set_audio(audio)
    video.write_videofile(
        str(mp4_path),
        fps=24,
        codec="libx264",
        audio_codec="aac",
        threads=2,
        preset="medium",
        verbose=False,
        logger=None,
    )

    video.close()
    audio.close()


def _load_fonts():
    font_size_active = Config.VIDEO_FONT_SIZE
    font_size_secondary = max(34, font_size_active - 18)
    candidates_active = ["arialbd.ttf", "Arial Bold.ttf", "Arial.ttf"]
    candidates_secondary = ["arial.ttf", "Arial.ttf"]

    active_font = None
    for candidate in candidates_active:
        try:
            active_font = ImageFont.truetype(candidate, font_size_active)
            break
        except OSError:
            continue
    if active_font is None:
        active_font = ImageFont.load_default()

    secondary_font = None
    for candidate in candidates_secondary:
        try:
            secondary_font = ImageFont.truetype(candidate, font_size_secondary)
            break
        except OSError:
            continue
    if secondary_font is None:
        secondary_font = ImageFont.load_default()

    return active_font, secondary_font


def _find_active_caption_index(captions: list[dict], current_ms: int) -> int:
    low = 0
    high = len(captions) - 1
    best = 0
    while low <= high:
        mid = (low + high) // 2
        line = captions[mid]
        if line["startMs"] <= current_ms <= line["endMs"]:
            return mid
        if current_ms < line["startMs"]:
            high = mid - 1
        else:
            best = mid
            low = mid + 1
    return min(best + 1, len(captions) - 1)


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    center_y: int,
    font: ImageFont.ImageFont,
    color: tuple[int, int, int, int],
    canvas_width: int,
    shadow: bool = False,
):
    if not text:
        return

    bbox = draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    x = max((canvas_width - width) // 2, 20)
    y = center_y - (height // 2)

    if shadow:
        draw.text((x + 2, y + 3), text, font=font, fill=(0, 0, 0, 140))
    draw.text((x, y), text, font=font, fill=color)
