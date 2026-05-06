import os
import threading
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from flask import Blueprint, request, send_file
from moviepy.editor import AudioFileClip, VideoClip

from config import Config
from routes import error_response, success_response
from services.job_manager import get_full_job_data, update_job

download_bp = Blueprint("download", __name__)
_video_locks: dict[str, threading.Lock] = {}

# Sync offset: positive = highlight appears later, negative = highlight appears earlier
# Set to 0 for accurate edge-tts timing
WORD_TIMING_OFFSET_MS = 0


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


@download_bp.route("/download/<job_id>/video", methods=["POST"])
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

    # Accept style config from request
    style_config = {}
    target_language = "en"
    urdu_font = None
    try:
        if request.is_json:
            data = request.get_json(silent=True)
            if data:
                style_config = data.get("style", {})
                target_language = data.get("target_language", "en")
                urdu_font = data.get("urdu_font", None)
    except Exception as e:
        print(f"[DOWNLOAD] Error parsing style config: {e}")

    print(f"[DOWNLOAD] Style config received: {style_config}")
    print(f"[DOWNLOAD] Target language: {target_language}, Urdu font: {urdu_font}")

    # If Urdu selected, update font to Urdu font
    if target_language == "ur" and urdu_font:
        style_config["font"] = urdu_font
        print(f"[DOWNLOAD] Using Urdu font: {urdu_font}")

    update_job(
        job_id,
        video_status="generating",
        video_progress=0,
        video_render_version=Config.VIDEO_RENDER_VERSION,
        video_error=None,
        video_style=style_config,
        target_language=target_language,
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


# Pre-calculated caption render data
CaptionRenderData = dict
# Keys: font, lines (for word-level), wrapped_lines (for line-level), etc.

def _precalculate_caption_data(captions: list[dict], resolution: tuple, style: dict, font_value: str, target_language: str = "en"):
    """Precalculate font sizes and word wrapping for all captions ONCE before rendering."""
    SAFE_MARGIN = 120
    SAFE_WIDTH = resolution[0] - 2 * SAFE_MARGIN
    font_size = style.get("fontSize", None)  # None = auto-fit

    # Create a scratch draw object for measurements
    scratch_img = Image.new("RGBA", (1, 1))
    scratch_draw = ImageDraw.Draw(scratch_img)

    caption_data = {}

    for idx, cap in enumerate(captions):
        text = cap.get("text", "")
        if not text:
            caption_data[idx] = {"font": _get_cached_font(font_value, 24, target_language), "lines": [], "wrapped_lines": []}
            continue

        # Calculate font - use user-specified size or auto-fit
        if font_size and 24 <= font_size <= 120:
            font = _get_cached_font(font_value, font_size, target_language)
        else:
            # Auto-fit: find largest font that fits
            fitted_font = None
            for size in range(48, 23, -2):
                test_font = _get_cached_font(font_value, size, target_language)
                test_lines = _wrap_text(scratch_draw, text, test_font, SAFE_WIDTH)
                if not test_lines:
                    break
                line_boxes = [scratch_draw.textbbox((0,0), line, font=test_font) for line in test_lines]
                total_h = sum(b[3] - b[1] for b in line_boxes) + 10 * (len(test_lines) - 1)
                if total_h <= resolution[1] * 0.3:  # Rough height check
                    max_lw = max(scratch_draw.textbbox((0,0), line, font=test_font)[2] for line in test_lines)
                    if max_lw <= SAFE_WIDTH:
                        fitted_font = test_font
                        break
            font = fitted_font if fitted_font else _get_cached_font(font_value, 24, target_language)

        # Pre-calculate word wrapping for word-level rendering
        words = cap.get("word_entries", [])
        valid_words = [w for w in words if w.get("endMs", 0) > w.get("startMs", 0) and w.get("word", "").strip()]
        lines = []
        if valid_words:
            current_line = []
            current_line_width = 0
            spacing = _calculate_word_spacing(font)
            for w in valid_words:
                word_width = scratch_draw.textbbox((0,0), w["word"], font=font)[2]
                if current_line:
                    test_width = current_line_width + spacing + word_width
                    if test_width <= SAFE_WIDTH:
                        current_line.append(w)
                        current_line_width = test_width
                    else:
                        lines.append(current_line)
                        current_line = [w]
                        current_line_width = word_width
                else:
                    current_line.append(w)
                    current_line_width = word_width
            if current_line:
                lines.append(current_line)

        # Pre-calculate line wrapping for line-level rendering
        wrapped_lines = _wrap_text(scratch_draw, text, font, SAFE_WIDTH)

        caption_data[idx] = {
            "font": font,
            "word_lines": lines,
            "wrapped_lines": wrapped_lines,
        }

    return caption_data


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

    # Read style config
    style = job.get("video_style", {})
    bg = _hex_to_rgb(style.get("bg", "#020617"))
    bg_start = _hex_to_rgb(style.get("bgStart", "#1e293b"))
    inactive = _hex_to_rgb(style.get("inactiveColor", "#4b5563"))
    active = _hex_to_rgb(style.get("activeColor", "#ffffff"))
    active_style = style.get("activeStyle", "color")
    layout = style.get("layout", "single")
    font_value = style.get("font", "'Inter', sans-serif")
    font_size = style.get("fontSize", None)  # None = auto-fit
    word_highlight = style.get("wordHighlight", True)
    target_language = job.get("target_language", "en")

    background = _make_preview_background(resolution, bg_start, bg)
    audio = AudioFileClip(str(mp3_path))
    update_job(job_id, video_progress=5)
    last_progress = 5

    # PRE-CALCULATE: font sizes, word wrapping, line wrapping
    update_job(job_id, video_progress=7)
    caption_data = _precalculate_caption_data(captions, resolution, style, font_value, target_language)
    update_job(job_id, video_progress=10)

    # Layout renderer dispatch
    layout_map = {
        "multi": _render_multi_line,
        "single": _render_single_line,
        "typewriter": _render_typewriter,
        "center": _render_center_focus,
        "banner": _render_bottom_banner,
        "full-page": _render_full_page,
    }
    render_fn = layout_map.get(layout, _render_single_line)

    def make_frame(t: float):
        nonlocal last_progress
        current_ms = int(t * 1000)
        active_idx = _find_active_caption_index(captions, current_ms)

        progress = min(95, 10 + int((t / max(audio.duration, 0.001)) * 85))
        if progress > last_progress:
            last_progress = progress
            update_job(job_id, video_progress=progress)

        frame = background.copy()
        draw = ImageDraw.Draw(frame)

        render_fn(draw, captions, active_idx, current_ms, resolution, active, inactive, active_style, font_value, word_highlight, caption_data)

        return np.array(frame.convert("RGB"))

    video = None
    try:
        video = VideoClip(make_frame, duration=audio.duration).set_audio(audio)
        video.write_videofile(
            str(mp4_path),
            fps=Config.VIDEO_FPS,
            codec="libx264",
            audio_codec="aac",
            threads=4,  # Increased from 2 for faster encoding
            preset="fast",  # Changed from medium for faster rendering
            verbose=False,
            logger=None,
        )
        update_job(job_id, video_progress=100)
    finally:
        if video:
            video.close()
        audio.close()


def _make_preview_background(resolution: tuple[int, int], bg_start: tuple = None, bg_end: tuple = None) -> Image.Image:
    width, height = resolution
    y, x = np.ogrid[:height, :width]

    if bg_start and bg_end:
        # Use custom colors
        center_x = width * 0.2
        center_y = height * 0.2
        distance = np.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
        radius = np.sqrt(width**2 + height**2) * 0.62
        amount = np.clip(distance / radius, 0, 1)

        start = np.array(bg_start, dtype=np.float32)
        end = np.array(bg_end, dtype=np.float32)

        pixels = np.empty((height, width, 3), dtype=np.uint8)
        t = np.clip(amount, 0, 1)[..., None]
        pixels = (start + (end - start) * t).astype(np.uint8)
    else:
        # Default gradient
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


# Font cache to avoid loading from disk on every call
_FONT_CACHE: dict[str, ImageFont.ImageFont] = {}

def _get_cached_font(font_value: str, size: int, target_language: str = "en") -> ImageFont.ImageFont:
    """Load font with fallback, with caching."""
    key = f"{font_value}_{size}_{target_language}"
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]

    font_name = font_value.split(",")[0].strip().strip("'\"")
    candidates = [font_name + ".ttf", font_name + ".ttc", font_name + ".otf"]
    
    # Add Urdu font paths if target language is Urdu
    if target_language == "ur":
        static_fonts_dir = Config.STATIC_FOLDER / "fonts"
        candidates.insert(0, str(static_fonts_dir / "noto-nastaliq-urdu.otf"))
        candidates.insert(1, str(static_fonts_dir / font_name + ".otf"))
    
    # Add common Windows font paths
    windows_fonts = [
        "C:\\Windows\\Fonts\\" + f for f in [
            "arial.ttf", "ARIAL.TTF", "georgia.ttf", "GEORGIA.TTF",
            "cour.ttf", "COUR.TTF", "verdana.ttf", "VERDANA.TTF",
            "trebuc.ttf", "TREBUC.TTF", "comic.ttf", "COMIC.TTF",
            "impact.ttf", "IMPACT.TTF"
        ]
    ]
    candidates.extend(windows_fonts)

    for candidate in candidates:
        try:
            font = ImageFont.truetype(candidate, size)
            _FONT_CACHE[key] = font
            return font
        except OSError:
            continue
    default_font = ImageFont.load_default()
    _FONT_CACHE[key] = default_font
    return default_font


def _find_active_caption_index(captions: list[dict], current_ms: int) -> int:
    """Find active caption index. Handles gaps by returning the caption that just ended."""
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
    # If past all captions, return last index
    if current_ms >= captions[-1]["endMs"]:
        return len(captions) - 1
    # If before all captions, return first index
    if current_ms <= captions[0]["startMs"]:
        return 0
    # In a gap - return the caption that just ended
    return best


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


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def _load_font_with_fallback(font_value: str, size: int, target_language: str = "en") -> ImageFont.ImageFont:
    """Load font with fallback to system fonts."""
    font_name = font_value.split(",")[0].strip().strip("'\"")
    candidates = [font_name + ".ttf", font_name + ".ttc", font_name + ".otf"]
    
    # Add Urdu font paths if target language is Urdu
    if target_language == "ur":
        static_fonts_dir = Config.STATIC_FOLDER / "fonts"
        candidates.insert(0, str(static_fonts_dir / "noto-nastaliq-urdu.otf"))
        candidates.insert(1, str(static_fonts_dir / font_name + ".otf"))
    
    # Add common Windows font paths
    windows_fonts = [
        "C:\\Windows\\Fonts\\" + f for f in [
            "arial.ttf", "ARIAL.TTF", "georgia.ttf", "GEORGIA.TTF",
            "cour.ttf", "COUR.TTF", "verdana.ttf", "VERDANA.TTF",
            "trebuc.ttf", "TREBUC.TTF", "comic.ttf", "COMIC.TTF",
            "impact.ttf", "IMPACT.TTF"
        ]
    ]
    candidates.extend(windows_fonts)

    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _fit_font(draw, text: str, max_width: int, max_height: int,
             font_value: str, min_size: int = 24, max_size: int = 48) -> tuple[ImageFont.ImageFont, int]:
    """Find the largest font size that fits within width and height constraints.
    Uses caller's min_size/max_size parameters."""
    for size in range(max_size, min_size - 1, -2):
        font = _get_cached_font(font_value, size)
        lines = _wrap_text(draw, text, font, max_width)
        if not lines:
            return font, size
        line_boxes = [draw.textbbox((0,0), line, font=font) for line in lines]
        total_height = sum(b[3] - b[1] for b in line_boxes) + 10 * (len(lines) - 1)
        if total_height <= max_height:
            # Check width too
            max_line_width = max(draw.textbbox((0,0), line, font=font)[2] for line in lines)
            if max_line_width <= max_width:
                return font, size
    return _get_cached_font(font_value, min_size), min_size


def _inverse_color(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    """Get contrasting text color (black or white) for a given background color."""
    luminance = (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / 255
    return (0, 0, 0) if luminance > 0.5 else (255, 255, 255)


def _draw_text_with_glow(draw, x: int, y: int, text: str, font, color: tuple, glow_intensity: int = 8):
    """Draw text with a clean glow effect using blurred outline."""
    r, g, b = color
    # Create a soft glow by drawing slightly blurred copies at increasing offsets
    # Use a subtle approach: draw the text multiple times with low alpha at offset positions
    glow_color = (r, g, b, glow_intensity * 10)  # Outer glow (low alpha)
    glow_offsets = [(-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, -1), (-1, 1), (1, 1)]

    for ox, oy in glow_offsets:
        draw.text((x + ox, y + oy), text, font=font, fill=glow_color)

    # Inner glow (slightly brighter)
    inner_glow = (r, g, b, glow_intensity * 18)
    draw.text((x, y), text, font=font, fill=inner_glow)

    # Main text (full opacity)
    draw.text((x, y), text, font=font, fill=(r, g, b, 255))


def _calculate_word_spacing(font) -> int:
    """Calculate spacing between words based on font metrics."""
    bbox = font.getbbox("A")
    return max(6, int((bbox[2] - bbox[0]) * 0.35))


# Layout Renderers

def _render_multi_line(draw, captions, active_idx, current_ms, resolution, active_color, inactive_color, active_style, font_value, word_highlight=True, caption_data=None):
    """Render 3 lines: prev/active/next with proper vertical spacing."""
    prev_line = captions[active_idx - 1]["text"] if active_idx > 0 else ""
    active_line = captions[active_idx]["text"]
    next_line = captions[active_idx + 1]["text"] if active_idx < len(captions) - 1 else ""

    center_y = resolution[1] // 2
    line_spacing = int(resolution[1] * 0.18)  # 18% of screen height between lines

    # Use pre-calculated fonts from caption_data
    active_cd = caption_data.get(active_idx, {}) if caption_data else {}
    active_font = active_cd.get("font", _get_cached_font(font_value, 24))
    active_wrapped = active_cd.get("wrapped_lines", [])
    active_word_lines = active_cd.get("word_lines", [])

    prev_cd = caption_data.get(active_idx - 1, {}) if active_idx > 0 and caption_data else {}
    prev_font = prev_cd.get("font", _get_cached_font(font_value, 24))
    prev_wrapped = prev_cd.get("wrapped_lines", [])

    next_cd = caption_data.get(active_idx + 1, {}) if active_idx < len(captions) - 1 and caption_data else {}
    next_font = next_cd.get("font", _get_cached_font(font_value, 24))
    next_wrapped = next_cd.get("wrapped_lines", [])

    # Clamp Y positions to prevent text from escaping screen edges
    top_y = max(60, center_y - line_spacing)
    bottom_y = min(resolution[1] - 60, center_y + line_spacing)

    _draw_caption_line(draw, prev_line, top_y, prev_font, (*inactive_color, 95), resolution[0], active_style, inactive_color, font_value, word_highlight=word_highlight, wrapped_lines=prev_wrapped)
    _draw_caption_line(draw, active_line, center_y, active_font, (*active_color, 255), resolution[0], active_style, active_color, font_value, shadow=True, is_active=True, caption=captions[active_idx], current_ms=current_ms, word_highlight=word_highlight, wrapped_lines=active_wrapped, word_lines=active_word_lines)
    _draw_caption_line(draw, next_line, bottom_y, next_font, (*inactive_color, 200), resolution[0], active_style, inactive_color, font_value, word_highlight=word_highlight, wrapped_lines=next_wrapped)


def _render_single_line(draw, captions, active_idx, current_ms, resolution, active_color, inactive_color, active_style, font_value, word_highlight=True, caption_data=None):
    """Render only the active line, centered. Uses SAFE_MARGIN=120px each side."""
    active_line = captions[active_idx]["text"]
    center_y = resolution[1] // 2  # Proper center (540 for 1080p)

    # Use pre-calculated font and wrapped_lines
    cd = caption_data.get(active_idx, {}) if caption_data else {}
    font = cd.get("font", _get_cached_font(font_value, 24))
    wrapped_lines = cd.get("wrapped_lines", [])
    word_lines = cd.get("word_lines", [])

    _draw_caption_line(draw, active_line, center_y, font, (*active_color, 255), resolution[0], active_style, active_color, font_value, shadow=True, is_active=True, caption=captions[active_idx], current_ms=current_ms, word_highlight=word_highlight, wrapped_lines=wrapped_lines, word_lines=word_lines)


def _render_typewriter(draw, captions, active_idx, current_ms, resolution, active_color, inactive_color, active_style, font_value, word_highlight=True, caption_data=None):
    """Typewriter mode: words appear sequentially with different opacities. Uses SAFE_MARGIN and pre-calculated word_lines."""
    caption = captions[active_idx]

    # If word highlighting is disabled, fall back to standard line rendering
    if not word_highlight:
        active_line = caption["text"]
        center_y = resolution[1] // 2
        SAFE_MARGIN = 120
        cd = caption_data.get(active_idx, {}) if caption_data else {}
        font = cd.get("font", _get_cached_font(font_value, 24))
        wrapped_lines = cd.get("wrapped_lines", [])
        _draw_caption_line(draw, active_line, center_y, font, (*active_color, 255), resolution[0], active_style, active_color, font_value, shadow=True, is_active=True, caption=caption, current_ms=current_ms, word_highlight=False, wrapped_lines=wrapped_lines)
        return

    # Use pre-calculated font and word_lines from caption_data
    cd = caption_data.get(active_idx, {}) if caption_data else {}
    font = cd.get("font", _get_cached_font(font_value, 24))
    word_lines = cd.get("word_lines", [])
    SAFE_MARGIN = 120
    SAFE_WIDTH = resolution[0] - 2 * SAFE_MARGIN

    if not word_lines:
        return

    # Calculate font height for vertical centering
    test_bbox = draw.textbbox((0, 0), "Ay", font=font)
    line_height = test_bbox[3] - test_bbox[1]
    line_spacing = max(10, int(line_height * 0.4))
    total_height = len(word_lines) * line_height + (len(word_lines) - 1) * line_spacing
    center_y = resolution[1] // 2
    current_y = center_y - (total_height // 2)

    # Adjust for Pillow baseline
    baseline_offset = (test_bbox[1] + test_bbox[3]) / 2
    current_y = int(current_y - baseline_offset)

    # Flatten word_lines to get all words in order
    all_words = []
    for line in word_lines:
        all_words.extend(line)

    # Find active word
    active_word_idx = -1
    for idx, w in enumerate(all_words):
        if w["startMs"] <= current_ms <= w["endMs"]:
            active_word_idx = idx
            break

    # Draw each line
    spacing = _calculate_word_spacing(font)
    for line in word_lines:
        line_width = sum(draw.textbbox((0,0), w["word"], font=font)[2] for w in line) + spacing * (len(line) - 1)
        x = max(SAFE_MARGIN, (resolution[0] - line_width) // 2)

        for w in line:
            is_past = current_ms > w["endMs"]
            is_active = (w == all_words[active_word_idx]) if active_word_idx >= 0 else False
            is_future = current_ms < w["startMs"]

            if is_past:
                opacity = 155  # 60% of 255
            elif is_active:
                opacity = 255
            else:
                opacity = 77  # 30% of 255

            color = active_color if (is_active or is_past) else inactive_color
            text_color = (*color, opacity)

            bbox = draw.textbbox((x, current_y), w["word"], font=font)
            word_width = bbox[2] - bbox[0]

            if is_active:
                if active_style == "underline":
                    draw.line([(bbox[0], bbox[3] + 4), (bbox[2], bbox[3] + 4)], fill=(*color, opacity), width=3)
                elif active_style == "glow":
                    _draw_text_with_glow(draw, x, current_y, w["word"], font, color)
                elif active_style == "block":
                    pad = 6
                    draw.rectangle([bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad], fill=(*color, 200))
                    text_color_inv = (*_inverse_color(color), 255)
                    draw.text((x, current_y), w["word"], font=font, fill=text_color_inv)
                    text_color = None

            if text_color is not None:
                draw.text((x, current_y), w["word"], font=font, fill=text_color)

            x += word_width + spacing

        current_y += line_height + line_spacing


def _render_center_focus(draw, captions, active_idx, current_ms, resolution, active_color, inactive_color, active_style, font_value, word_highlight=True, caption_data=None):
    """Render 5 lines: 2 prev (dim), active (bright), 2 next (dimmer). Uses SAFE_MARGIN=120px each side."""
    lines_to_show = []
    for i in range(max(0, active_idx - 2), min(len(captions), active_idx + 3)):
        lines_to_show.append(i)

    center_y = resolution[1] // 2
    line_spacing = resolution[1] // 6  # Increased spacing to prevent overlap

    for offset, line_idx in enumerate(lines_to_show):
        line = captions[line_idx]
        y = center_y + (offset - 2) * line_spacing

        # Clamp y to prevent text from escaping screen edges
        y = max(60, min(resolution[1] - 60, y))

        # Use pre-calculated font from caption_data
        cd = caption_data.get(line_idx, {}) if caption_data else {}
        font = cd.get("font", _get_cached_font(font_value, 24))
        wrapped_lines = cd.get("wrapped_lines", [])

        if line_idx < active_idx:
            opacity = 100 - (active_idx - line_idx) * 30
            color = inactive_color
        elif line_idx == active_idx:
            opacity = 255
            color = active_color
        else:
            opacity = 80 - (line_idx - active_idx) * 20
            color = inactive_color

        _draw_caption_line(draw, line["text"], y, font, (*color, max(30, opacity)), resolution[0], active_style, color, font_value, is_active=(line_idx == active_idx), caption=line, current_ms=current_ms, word_highlight=word_highlight, wrapped_lines=wrapped_lines)


def _render_bottom_banner(draw, captions, active_idx, current_ms, resolution, active_color, inactive_color, active_style, font_value, word_highlight=True, caption_data=None):
    """Render active line in a semi-transparent banner at the bottom."""
    active_line = captions[active_idx]["text"]
    banner_height = int(resolution[1] * 0.15)
    banner_y = resolution[1] - banner_height
    center_y = banner_y + banner_height // 2

    # Draw semi-transparent banner
    for i in range(10):
        alpha = int(150 * (10 - i) / 10)
        draw.rectangle([0, banner_y + i, resolution[0], resolution[1] - i], fill=(0, 0, 0, alpha))

    # Use pre-calculated font and wrapped_lines from caption_data
    cd = caption_data.get(active_idx, {}) if caption_data else {}
    font = cd.get("font", _get_cached_font(font_value, 24))
    wrapped_lines = cd.get("wrapped_lines", [])

    _draw_caption_line(draw, active_line, center_y, font, (*active_color, 255), resolution[0], active_style, active_color, font_value, shadow=True, is_active=True, caption=captions[active_idx], current_ms=current_ms, word_highlight=word_highlight, wrapped_lines=wrapped_lines)


def _render_full_page(draw, captions, active_idx, current_ms, resolution, active_color, inactive_color, active_style, font_value, word_highlight=True, caption_data=None):
    """Render active line dominating the screen with large text."""
    active_line = captions[active_idx]["text"]
    center_y = resolution[1] // 2

    # Use pre-calculated font and wrapped_lines from caption_data
    cd = caption_data.get(active_idx, {}) if caption_data else {}
    font = cd.get("font", _get_cached_font(font_value, 24))
    wrapped_lines = cd.get("wrapped_lines", [])

    _draw_caption_line(draw, active_line, center_y, font, (*active_color, 255), resolution[0], active_style, active_color, font_value, shadow=True, is_active=True, caption=captions[active_idx], current_ms=current_ms, word_highlight=word_highlight, wrapped_lines=wrapped_lines)


def _draw_caption_line(draw, text: str, y: int, font, color: tuple, canvas_width: int, active_style: str, active_color: tuple, font_value: str, shadow: bool = False, is_active: bool = False, caption: dict = None, current_ms: int = 0, word_highlight: bool = True, wrapped_lines: list = None, word_lines: list = None):
    """Draw a caption line centered at y coordinate (y is the vertical center of the text block).
    Uses SAFE_MARGIN of 120px from each side."""
    if not text:
        return

    # Safe area: 120px margin on each side
    SAFE_MARGIN = 120
    max_text_width = canvas_width - 2 * SAFE_MARGIN  # 1680 for 1920 wide

    # Use pre-calculated wrapped_lines if provided, otherwise calculate
    if wrapped_lines is None:
        wrapped_lines = _wrap_text(draw, text, font, max_text_width)
    if not wrapped_lines:
        return

    line_boxes = [draw.textbbox((0,0), line, font=font) for line in wrapped_lines]
    line_heights = [bbox[3] - bbox[1] for bbox in line_boxes]
    line_spacing = max(12, int(sum(line_heights) / max(1, len(line_heights)) * 0.4))
    total_height = sum(line_heights) + line_spacing * (len(line_heights) - 1)

    if is_active and caption and "word_entries" in caption and word_highlight:
        # Word-level rendering - y is the center of the text block
        _draw_word_level(draw, caption, current_ms, y, font, active_color, color, active_style, canvas_width, word_lines=word_lines)
    else:
        # Line-level rendering - center the block of text at y
        # Pillow: draw.text((x,y),...) places BASELINE at y
        # Calculate offset so text block is centered at y
        test_bbox = draw.textbbox((0,0), "Ay", font=font)
        center_offset = (test_bbox[1] + test_bbox[3]) / 2
        current_y = int(y - total_height // 2 - center_offset)
        for line, bbox, line_height in zip(wrapped_lines, line_boxes, line_heights):
            line_width = bbox[2] - bbox[0]
            x = max(SAFE_MARGIN, (canvas_width - line_width) // 2)
            if shadow:
                draw.text((x + 2, current_y + 3), line, font=font, fill=(0, 0, 0, 140))
            if is_active and active_style == "glow":
                _draw_text_with_glow(draw, x, current_y, line, font, active_color[:3])
            else:
                draw.text((x, current_y), line, font=font, fill=color)
            current_y += line_height + line_spacing


def _draw_word_level(draw, caption: dict, current_ms: int, center_y: int, font, active_color: tuple, inactive_color: tuple, active_style: str, canvas_width: int, word_lines: list = None):
    """Draw a caption line with word-level highlighting. center_y is the vertical CENTER of the text block.
    Uses pre-calculated word_lines from caption_data if provided."""
    # Use pre-calculated word_lines if provided
    lines = word_lines if word_lines else []

    if not lines:
        # Fallback: filter and group words (shouldn't happen if pre-calculated)
        words = caption.get("word_entries", [])
        if not words:
            return
        valid_words = [w for w in words if w.get("endMs", 0) > w.get("startMs", 0) and w.get("word", "").strip()]
        if not valid_words:
            return
        # Group words into lines
        SAFE_MARGIN = 120
        max_line_width = canvas_width - 2 * SAFE_MARGIN
        lines = []
        current_line = []
        current_line_width = 0
        spacing = _calculate_word_spacing(font)
        for w in valid_words:
            word_width = draw.textbbox((0, 0), w["word"], font=font)[2]
            if current_line:
                test_width = current_line_width + spacing + word_width
                if test_width <= max_line_width:
                    current_line.append(w)
                    current_line_width = test_width
                else:
                    lines.append(current_line)
                    current_line = [w]
                    current_line_width = word_width
            else:
                current_line.append(w)
                current_line_width = word_width
        if current_line:
            lines.append(current_line)
        if not lines:
            return

    # Calculate line height and total block height
    test_bbox = draw.textbbox((0, 0), "Ay", font=font)
    line_height = test_bbox[3] - test_bbox[1]
    line_spacing = max(10, int(line_height * 0.4))
    total_height = len(lines) * line_height + (len(lines) - 1) * line_spacing

    # Center the block of lines at center_y
    current_y = center_y - (total_height // 2)
    # Adjust for Pillow baseline: draw.text() places baseline at y
    baseline_offset = (test_bbox[1] + test_bbox[3]) / 2
    current_y = int(current_y - baseline_offset)

    # Find active word to determine which word to highlight
    active_word_info = None
    for line_idx, line in enumerate(lines):
        for word_idx, w in enumerate(line):
            if w["startMs"] <= current_ms <= w["endMs"]:
                active_word_info = (line_idx, word_idx, w)
                break
        if active_word_info:
            break

    # Draw each line
    spacing = _calculate_word_spacing(font)
    for line_idx, line in enumerate(lines):
        # Calculate line width
        line_width = sum(draw.textbbox((0, 0), w["word"], font=font)[2] for w in line) + spacing * (len(line) - 1)
        SAFE_MARGIN = 120
        x = max(SAFE_MARGIN, (canvas_width - line_width) // 2)

        for word_idx, w in enumerate(line):
            is_active = (active_word_info and active_word_info[0] == line_idx and active_word_info[1] == word_idx)
            color = active_color if is_active else inactive_color[:3]
            text_color = (*color, 255)

            bbox = draw.textbbox((x, current_y), w["word"], font=font)
            word_width = bbox[2] - bbox[0]

            if is_active:
                if active_style == "underline":
                    draw.line([(bbox[0], bbox[3] + 4), (bbox[2], bbox[3] + 4)], fill=(*color, 255), width=3)
                elif active_style == "glow":
                    _draw_text_with_glow(draw, x, current_y, w["word"], font, color)
                elif active_style == "block":
                    pad = 6
                    draw.rectangle([bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad], fill=(*color, 200))
                    text_color_inv = (*_inverse_color(color), 255)
                    draw.text((x, current_y), w["word"], font=font, fill=text_color_inv)
                    text_color = None

            if text_color is not None:
                draw.text((x, current_y), w["word"], font=font, fill=text_color)

            x += word_width + spacing

        current_y += line_height + line_spacing
