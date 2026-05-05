import re
from pathlib import Path


def format_vtt_time(ms: int) -> str:
    s, ms = divmod(max(ms, 0), 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def _normalize_word(word: str) -> str:
    return re.sub(r"\s+", " ", word).strip()


def _join_words(words: list[str]) -> str:
    text = " ".join(words)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"\s+'", "'", text)
    return text.strip()


def build_caption_lines(
    word_entries: list[dict],
    min_words: int,
    max_words: int,
    max_gap_ms: int,
) -> list[dict]:
    if not word_entries:
        return []

    lines: list[dict] = []
    bucket: list[dict] = []

    for idx, word_entry in enumerate(word_entries):
        token = _normalize_word(word_entry.get("word", ""))
        if not token:
            continue

        current = {
            "word": token,
            "startMs": int(word_entry["startMs"]),
            "endMs": int(word_entry["endMs"]),
        }
        bucket.append(current)

        next_entry = word_entries[idx + 1] if idx + 1 < len(word_entries) else None
        next_gap_ms = None
        if next_entry:
            next_gap_ms = int(next_entry["startMs"]) - int(current["endMs"])

        reached_min = len(bucket) >= min_words
        reached_max = len(bucket) >= max_words
        punctuation_break = token.endswith((".", "!", "?", ";", ":"))
        long_gap_break = next_gap_ms is not None and next_gap_ms > max_gap_ms
        last_word = next_entry is None

        if reached_max or (reached_min and (punctuation_break or long_gap_break or last_word)):
            lines.append(
                {
                    "startMs": bucket[0]["startMs"],
                    "endMs": bucket[-1]["endMs"],
                    "text": _join_words([entry["word"] for entry in bucket]),
                    "word_entries": list(bucket),
                    "words": len(bucket),
                }
            )
            bucket = []

    if bucket:
        # Merge short tail into previous line where possible.
        if lines and len(bucket) < min_words and (int(lines[-1]["words"]) + len(bucket) <= max_words):
            merged_text = _join_words(
                [lines[-1]["text"]] + [entry["word"] for entry in bucket]
            )
            lines[-1]["text"] = merged_text
            lines[-1]["endMs"] = bucket[-1]["endMs"]
            lines[-1]["word_entries"].extend(bucket)
            lines[-1]["words"] = int(lines[-1]["words"]) + len(bucket)
        else:
            lines.append(
                {
                    "startMs": bucket[0]["startMs"],
                    "endMs": bucket[-1]["endMs"],
                    "text": _join_words([entry["word"] for entry in bucket]),
                    "word_entries": list(bucket),
                    "words": len(bucket),
                }
            )

    # Assign stable indices for frontend sync and video rendering.
    for idx, line in enumerate(lines):
        line["index"] = idx

    return lines


def write_word_vtt(path: Path, entries: list[dict]):
    with open(path, "w", encoding="utf-8") as file_obj:
        file_obj.write("WEBVTT\n\n")
        for idx, entry in enumerate(entries, 1):
            start = format_vtt_time(int(entry["startMs"]))
            end = format_vtt_time(int(entry["endMs"]))
            file_obj.write(f"{idx}\n")
            file_obj.write(f"{start} --> {end}\n")
            file_obj.write(f"{entry['word']}\n\n")


def write_line_vtt(path: Path, lines: list[dict]):
    with open(path, "w", encoding="utf-8") as file_obj:
        file_obj.write("WEBVTT\n\n")
        for idx, line in enumerate(lines, 1):
            start = format_vtt_time(int(line["startMs"]))
            end = format_vtt_time(int(line["endMs"]))
            file_obj.write(f"{idx}\n")
            file_obj.write(f"{start} --> {end}\n")
            file_obj.write(f"{line['text']}\n\n")
