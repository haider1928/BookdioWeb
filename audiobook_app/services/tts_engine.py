import asyncio
from pathlib import Path

import edge_tts
from mutagen.mp3 import MP3

from config import Config


def run_tts_job(job_id: str, chunks: list[str], voice: str, speed: str, update_job_fn, get_job_fn):
    asyncio.run(_async_tts_job(job_id, chunks, voice, speed, update_job_fn, get_job_fn))


async def _async_tts_job(job_id: str, chunks: list[str], voice: str, speed: str, update_job_fn, get_job_fn):
    from services.job_manager import append_to_vtt, rebuild_captions, write_vtt_file

    mp3_path = Path(get_job_fn(job_id)["mp3_path"])
    time_offset_ms = 0
    
    # Initialize the MP3 file
    with open(mp3_path, "wb") as f:
        pass

    for i, text_chunk in enumerate(chunks, 1):
        temp_mp3 = Config.OUTPUT_FOLDER / f"{job_id}_temp_{i}.mp3"
        
        success = False
        for attempt in range(Config.TTS_MAX_RETRIES + 1):
            try:
                communicate = edge_tts.Communicate(
                    text_chunk.strip(),
                    voice,
                    rate=speed,
                    boundary="WordBoundary",
                )
                new_entries = []
                
                with open(temp_mp3, "wb") as f:
                    async for chunk_data in communicate.stream():
                        if chunk_data["type"] == "audio":
                            f.write(chunk_data["data"])
                        elif chunk_data["type"] == "WordBoundary":
                            start_ms = time_offset_ms + int(chunk_data["offset"] / 10000)
                            duration_ms = max(1, int(chunk_data["duration"] / 10000))
                            end_ms = start_ms + duration_ms
                            token = str(chunk_data.get("text", "")).strip()
                            if token:
                                new_entries.append(
                                    {
                                        "word": token,
                                        "startMs": start_ms,
                                        "endMs": end_ms,
                                    }
                                )
                
                # Measure duration
                audio_info = MP3(temp_mp3)
                duration_ms = int(audio_info.info.length * 1000)
                
                # Fallback: if boundary events are unavailable, approximate from words.
                if not new_entries:
                    words = [word for word in text_chunk.split() if word.strip()]
                    if words:
                        slot_ms = max(1, duration_ms // len(words))
                        rolling_start = time_offset_ms
                        for word in words:
                            rolling_end = min(time_offset_ms + duration_ms, rolling_start + slot_ms)
                            new_entries.append(
                                {
                                    "word": word,
                                    "startMs": rolling_start,
                                    "endMs": rolling_end,
                                }
                            )
                            rolling_start = rolling_end
                
                append_to_vtt(job_id, new_entries)
                rebuild_captions(job_id)
                
                # Append to main MP3
                with open(temp_mp3, "rb") as source, open(mp3_path, "ab") as dest:
                    dest.write(source.read())
                
                time_offset_ms += duration_ms
                success = True
                break
            except Exception as e:
                print(f"Error in chunk {i}, attempt {attempt}: {e}")
                if attempt < Config.TTS_MAX_RETRIES:
                    await asyncio.sleep(1)
                else:
                    raise e
            finally:
                if temp_mp3.exists():
                    temp_mp3.unlink()

        if success:
            update_job_fn(job_id, chunks_done=i, preview_ready=True, time_offset_ms=time_offset_ms)

    # Finalize VTT
    rebuild_captions(job_id)
    write_vtt_file(job_id)
