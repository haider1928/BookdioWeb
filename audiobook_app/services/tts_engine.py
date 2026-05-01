import asyncio
from pathlib import Path
from time import time
from uuid import uuid4

import edge_tts

VOICE_CACHE = {
    "fetched_at": 0.0,
    "voices": [],
}
VOICE_CACHE_TTL_SECONDS = 60 * 60


def format_rate(speed) -> str:
    if speed is None or str(speed).strip() == "":
        value = 0
    elif isinstance(speed, str) and speed.strip().endswith("%"):
        value = float(speed.strip()[:-1])
    else:
        value = float(speed)

    if value < -50 or value > 50:
        raise ValueError("Speed must be between -50 and +50.")

    rounded = int(round(value))
    sign = "+" if rounded >= 0 else ""
    return f"{sign}{rounded}%"


def split_text_into_chunks(text: str, words_per_chunk: int) -> list[str]:
    words = text.split()
    if not words:
        return []

    return [
        " ".join(words[index : index + words_per_chunk])
        for index in range(0, len(words), words_per_chunk)
    ]


async def list_english_voices() -> list[dict]:
    voices = await edge_tts.list_voices()
    english_voices = []

    for voice in voices:
        locale = str(voice.get("Locale", ""))
        short_name = voice.get("ShortName")
        if not locale.lower().startswith("en-") or not short_name:
            continue

        english_voices.append(
            {
                "short_name": short_name,
                "gender": voice.get("Gender", "Neutral"),
                "name": voice.get("FriendlyName") or short_name,
                "locale": locale,
            }
        )

    english_voices.sort(key=lambda item: (item["gender"], item["locale"], item["name"]))
    return english_voices


async def get_english_voices(force_refresh: bool = False) -> list[dict]:
    now = time()
    cached_voices = VOICE_CACHE["voices"]
    fetched_at = VOICE_CACHE["fetched_at"]

    if cached_voices and not force_refresh and now - fetched_at < VOICE_CACHE_TTL_SECONDS:
        return cached_voices

    voices = await list_english_voices()
    VOICE_CACHE["voices"] = voices
    VOICE_CACHE["fetched_at"] = now
    return voices


def get_english_voices_sync(force_refresh: bool = False) -> list[dict]:
    return asyncio.run(get_english_voices(force_refresh=force_refresh))


def validate_voice(short_name: str, voices: list[dict]) -> bool:
    return short_name in {voice["short_name"] for voice in voices}


async def convert_text_to_mp3(text: str, voice: str, speed, output_folder: Path) -> dict:
    rate = format_rate(speed)
    filename = f"{uuid4().hex}.mp3"
    output_path = output_folder / filename

    await save_chunk_with_retries(text, voice, rate, output_path)

    return {
        "filename": filename,
        "path": output_path,
        "voice": voice,
        "speed": rate,
    }


def convert_text_to_mp3_sync(text: str, voice: str, speed, output_folder: Path) -> dict:
    return asyncio.run(convert_text_to_mp3(text, voice, speed, output_folder))


async def save_chunk_once(text: str, voice: str, rate: str, output_path: Path) -> None:
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate)
    await communicate.save(str(output_path))


async def save_chunk_with_retries(
    text: str,
    voice: str,
    rate: str,
    output_path: Path,
    timeout_seconds: int = 30,
    max_retries: int = 2,
) -> None:
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            if output_path.exists():
                output_path.unlink()
            await asyncio.wait_for(
                save_chunk_once(text, voice, rate, output_path),
                timeout=timeout_seconds,
            )
            return
        except Exception as exc:
            last_error = exc
            if output_path.exists():
                output_path.unlink()
            if attempt < max_retries:
                await asyncio.sleep(1)

    raise RuntimeError("EdgeTTS connection failed. Check internet connection or try again.") from last_error


def save_chunk_with_retries_sync(
    text: str,
    voice: str,
    rate: str,
    output_path: Path,
    timeout_seconds: int = 30,
    max_retries: int = 2,
) -> None:
    asyncio.run(
        save_chunk_with_retries(
            text,
            voice,
            rate,
            output_path,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )
    )
