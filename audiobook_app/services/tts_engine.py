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
                submaker = edge_tts.SubMaker()
                communicate = edge_tts.Communicate(text_chunk.strip(), voice, rate=speed)
                
                with open(temp_mp3, "wb") as f:
                    async for chunk_data in communicate.stream():
                        if chunk_data["type"] == "audio":
                            f.write(chunk_data["data"])
                        elif chunk_data["type"] in ["WordBoundary", "SentenceBoundary"]:
                            submaker.feed(chunk_data)
                
                # Measure duration
                audio_info = MP3(temp_mp3)
                duration_ms = int(audio_info.info.length * 1000)
                
                # Process VTT entries
                new_entries = []
                for cue in submaker.cues:
                    # cue.start and cue.end are timedelta objects in edge-tts 7.x
                    start_ms = time_offset_ms + int(cue.start.total_seconds() * 1000)
                    end_ms = time_offset_ms + int(cue.end.total_seconds() * 1000)
                    
                    new_entries.append({
                        "word": cue.content,
                        "startMs": start_ms,
                        "endMs": end_ms
                    })
                
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
