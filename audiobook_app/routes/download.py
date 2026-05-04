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
    render_version = job.get("video_render_version")
    if mp4_path.exists() and render_version == Config.VIDEO_RENDER_VERSION:
        update_job(job_id, video_status="done", video_progress=100, video_error=None)
        return success_response(
            {
                "video_status": "done",
                "video_progress": 100,
                "download_url": f"/download/{job_id}/video/file",
            }
        )
    if mp4_path.exists():
        mp4_path.unlink()

    if job["status"] != "done":
        return error_response("Job must be complete before video generation", 425)

    current_status = job.get("video_status", "idle")
    if current_status == "generating":
        return success_response(
            {
                "video_status": "generating",
                "video_progress": job.get("video_progress", 0),
            },
            202,
        )

    update_job(
        job_id,
        video_status="generating",
        video_progress=0,
        video_render_version=Config.VIDEO_RENDER_VERSION,
        video_error=None,
    )
    threading.Thread(target=_generate_video_safe, args=(job_id,), daemon=True).start()
    return success_response({"video_status": "generating", "video_progress": 0}, 202)


@download_bp.route("/download/<job_id>/video/status", methods=["GET"])
def video_status(job_id):
    job = get_full_job_data(job_id)
    if not job:
        return error_response("Job not found", 404)

    status = job.get("video_status", "idle")
    response = {
        "video_status": status,
        "video_progress": job.get("video_progress", 0),
        "video_error": job.get("video_error"),
    }
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
            update_job(job_id, video_status="done", video_progress=100, video_error=None)
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
    background = _make_preview_background(resolution)
    title_font, body_font = _load_fonts()
    audio = AudioFileClip(str(mp3_path))
    update_job(job_id, video_progress=5)
    last_progress = 5

    def make_frame(t: float):
        nonlocal last_progress
        current_ms = int(t * 1000)
        active_idx = _find_active_caption_index(captions, current_ms)
        prev_line = captions[active_idx - 1]["text"] if active_idx > 0 else ""
        active_line = captions[active_idx]["text"]
        next_line = captions[active_idx + 1]["text"] if active_idx < len(captions) - 1 else ""

        progress = min(95, 5 + int((t / max(audio.duration, 0.001)) * 90))
        if progress > last_progress:
            last_progress = progress
            update_job(job_id, video_progress=progress)

        frame = background.copy()
        draw = ImageDraw.Draw(frame)

        center_y = resolution[1] // 2
        _draw_centered_text(draw, prev_line, center_y - 150, body_font, (133, 147, 170, 95), resolution[0])
        _draw_centered_text(draw, active_line, center_y, title_font, (255, 255, 255, 255), resolution[0], shadow=True)
        _draw_centered_text(draw, next_line, center_y + 145, body_font, (185, 198, 216, 200), resolution[0])

        return np.array(frame.convert("RGB"))

    video = None
    try:
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
        update_job(job_id, video_progress=100)
    finally:
        if video:
            video.close()
        audio.close()


def _make_preview_background(resolution: tuple[int, int]) -> Image.Image:
    width, height = resolution
    y, x = np.ogrid[:height, :width]
    center_x = width * 0.2
    center_y = height * 0.2
    distance = np.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
    radius = np.sqrt(width**2 + height**2) * 0.62
    amount = np.clip(distance / radius, 0, 1)

    start = np.array([30, 41, 59], dtype=np.float32)
    mid = np.array([2, 6, 23], dtype=np.float32)
    end = np.array([0, 0, 0], dtype=np.float32)

    first_band = amount <= 0.6
    pixels = np.empty((height, width, 3), dtype=np.uint8)
    first_t = np.clip(amount / 0.6, 0, 1)[..., None]
    second_t = np.clip((amount - 0.6) / 0.4, 0, 1)[..., None]
    pixels[first_band] = (start + (mid - start) * first_t)[first_band]
    pixels[~first_band] = (mid + (end - mid) * second_t)[~first_band]

    alpha = np.full((height, width, 1), 255, dtype=np.uint8)
    return Image.fromarray(np.concatenate([pixels, alpha], axis=2), "RGBA")


def _load_fonts():
    font_size_active = Config.VIDEO_FONT_SIZE
    font_size_secondary = max(34, font_size_active - 6)
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

    max_text_width = int(canvas_width * 0.9)
    wrapped_lines = _wrap_text(draw, text, font, max_text_width)
    if not wrapped_lines:
        return

    line_boxes = [draw.textbbox((0, 0), line, font=font) for line in wrapped_lines]
    line_heights = [(bbox[3] - bbox[1]) for bbox in line_boxes]
    line_spacing = max(10, int(sum(line_heights) / max(1, len(line_heights)) * 0.3))
    total_height = sum(line_heights) + line_spacing * (len(line_heights) - 1)
    current_y = center_y - (total_height // 2)

    for line, bbox, line_height in zip(wrapped_lines, line_boxes, line_heights):
        line_width = bbox[2] - bbox[0]
        x = max((canvas_width - line_width) // 2, 20)
        if shadow:
            draw.text((x + 2, current_y + 3), line, font=font, fill=(0, 0, 0, 140))
        draw.text((x, current_y), line, font=font, fill=color)
        current_y += line_height + line_spacing


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return []

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        width = draw.textbbox((0, 0), candidate, font=font)[2]
        if width <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines
