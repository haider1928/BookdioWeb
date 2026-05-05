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
    semaphore = asyncio.Semaphore(Config.TTS_MAX_CONCURRENT_WORKERS)
    chunk_results = [None] * len(chunks)
    chunk_durations_ms = [0] * len(chunks)
    temp_mp3_paths = [Config.OUTPUT_FOLDER / f"{job_id}_temp_{i}.mp3" for i in range(len(chunks))]

    async def process_chunk(i, text_chunk):
        async with semaphore:
            temp_mp3 = temp_mp3_paths[i]
            for attempt in range(Config.TTS_MAX_RETRIES + 1):
                try:
                    communicate = edge_tts.Communicate(text_chunk.strip(), voice, rate=speed)
                    new_entries = []
                    with open(temp_mp3, "wb") as f:
                        async for chunk_data in communicate.stream():
                            if chunk_data["type"] == "audio":
                                f.write(chunk_data["data"])
                            elif chunk_data["type"] == "WordBoundary":
                                offset_ms = int(chunk_data["offset"] / 10000)
                                duration_ms = max(1, int(chunk_data["duration"] / 10000))
                                token = str(chunk_data.get("text", "")).strip()
                                if token:
                                    new_entries.append({
                                        "word": token,
                                        "offsetMs": offset_ms,
                                        "durationMs": duration_ms,
                                    })

                    audio_info = MP3(temp_mp3)
                    dur = int(audio_info.info.length * 1000)
                    chunk_durations_ms[i] = dur

                    if not new_entries:
                        words = [w for w in text_chunk.split() if w.strip()]
                        if words:
                            slot_ms = max(1, dur // len(words))
                            for wi, word in enumerate(words):
                                new_entries.append({
                                    "word": word,
                                    "offsetMs": wi * slot_ms,
                                    "durationMs": slot_ms,
                                })

                    chunk_results[i] = new_entries
                    update_job_fn(job_id, chunks_done=i + 1, preview_ready=True)
                    print(f"[TTS] Chunk {i+1}/{len(chunks)} done ({dur}ms)")
                    return
                except Exception as e:
                    print(f"[TTS] Error chunk {i+1}, attempt {attempt}: {e}")
                    if attempt < Config.TTS_MAX_RETRIES:
                        await asyncio.sleep(1)
                    else:
                        raise

    # Process all chunks in parallel
    tasks = [asyncio.create_task(process_chunk(i, chunk)) for i, chunk in enumerate(chunks)]
    await asyncio.gather(*tasks)

    # Sequential assembly: compute time offsets and build VTT
    time_offset_ms = 0
    with open(mp3_path, "wb") as f:
        pass

    all_vtt_entries = []
    for i in range(len(chunks)):
        entries = chunk_results[i]
        if entries is None:
            continue
        for entry in entries:
            start_ms = time_offset_ms + entry["offsetMs"]
            end_ms = start_ms + entry["durationMs"]
            all_vtt_entries.append({"word": entry["word"], "startMs": start_ms, "endMs": end_ms})

        # Append temp MP3 to main file
        with open(temp_mp3_paths[i], "rb") as src, open(mp3_path, "ab") as dest:
            dest.write(src.read())

        time_offset_ms += chunk_durations_ms[i]

    # Build VTT and captions once at the end
    append_to_vtt(job_id, all_vtt_entries)
    rebuild_captions(job_id)
    write_vtt_file(job_id)

    # Clean up temp files
    for p in temp_mp3_paths:
        if p.exists():
            p.unlink()

    print(f"[TTS] All {len(chunks)} chunks complete. Total duration: {time_offset_ms}ms")
