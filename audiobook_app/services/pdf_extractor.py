import re
import time
import fitz  # PyMuPDF
from spellchecker import SpellChecker

from config import Config

_LIGATURE_FIXES = {
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2013": "-",
    "\u2014": "-",
}


def normalize_text(text: str) -> str:
    """Clean OCR artifacts and normalize whitespace/punctuation."""
    for broken, fixed in _LIGATURE_FIXES.items():
        text = text.replace(broken, fixed)

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" +([,.;:!?])", r"\1", text)
    return text.strip()


def _split_sentences(text: str) -> list[str]:
    blocks = [block.strip() for block in text.split("\n\n") if block.strip()]
    sentences: list[str] = []
    for block in blocks:
        block = re.sub(r"\s*\n\s*", " ", block)
        parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", block)
        for part in parts:
            part = part.strip()
            if part:
                sentences.append(part)
    return sentences


def _should_skip_spellcheck(token: str) -> bool:
    if len(token) <= 2:
        return True
    if token.isupper():
        return True
    if token != token.lower():
        return True
    if any(ch.isdigit() for ch in token):
        return True
    return False


def _spell_correct_sentence(sentence: str, spell: SpellChecker) -> str:
    corrected: list[str] = []
    for token in sentence.split():
        match = re.match(r"^([\"'(\[]*)([A-Za-z][A-Za-z'-]*)([)\]\"'.,;:!?]*)$", token)
        if not match:
            corrected.append(token)
            continue

        prefix, core, suffix = match.groups()
        if _should_skip_spellcheck(core):
            corrected.append(token)
            continue

        candidate = spell.correction(core.lower())
        if not candidate or candidate == core.lower():
            corrected.append(token)
            continue

        if core[0].isupper():
            candidate = candidate.capitalize()
        corrected.append(f"{prefix}{candidate}{suffix}")

    sentence_text = " ".join(corrected)
    sentence_text = re.sub(r"\s+([,.;:!?])", r"\1", sentence_text)
    sentence_text = re.sub(r"\s+'", "'", sentence_text)
    sentence_text = re.sub(r"([.!?]){2,}", r"\1", sentence_text)
    sentence_text = re.sub(r",\s*,", ", ", sentence_text)
    sentence_text = re.sub(r"\s{2,}", " ", sentence_text).strip()

    if sentence_text and sentence_text[0].isalpha():
        sentence_text = sentence_text[0].upper() + sentence_text[1:]
    if sentence_text and sentence_text[-1] not in ".!?":
        sentence_text += "."
    return sentence_text


def _build_chunks(sentences: list[str], max_words: int) -> list[str]:
    chunks: list[str] = []
    current_sentences: list[str] = []
    current_words = 0

    for sentence in sentences:
        sentence_words = len(sentence.split())
        if current_sentences and (current_words + sentence_words) > max_words:
            chunks.append(" ".join(current_sentences).strip())
            current_sentences = [sentence]
            current_words = sentence_words
        else:
            current_sentences.append(sentence)
            current_words += sentence_words

    if current_sentences:
        chunks.append(" ".join(current_sentences).strip())
    return chunks


def extract_pdf_text(
    pdf_path: str | Path, 
    page_start: int | None = None, 
    page_end: int | None = None,
    progress_callback: callable | None = None
) -> dict:
    start_time = time.time()
    doc = fitz.open(str(pdf_path))
    page_count = doc.page_count

    if page_count == 0:
        doc.close()
        raise ValueError("PDF has no pages.")

    start_page = page_start or 1
    end_page = page_end or page_count
    if start_page < 1 or end_page < start_page or start_page > page_count:
        doc.close()
        raise ValueError(f"Invalid page range. PDF has {page_count} pages.")
    end_page = min(end_page, page_count)

    raw_text_parts = []
    total_pages_to_extract = end_page - start_page + 1
    
    for i, page_index in enumerate(range(start_page - 1, end_page)):
        page_text = doc[page_index].get_text()
        raw_text_parts.append(f"{page_text}\n")
        
        if progress_callback:
            progress_callback(i + 1, total_pages_to_extract)

    doc.close()
    raw_text = "".join(raw_text_parts)
    extract_time = time.time() - start_time
    print(f"PDF extraction took {extract_time:.2f}s")

    norm_start = time.time()
    normalized_text = normalize_text(raw_text)
    raw_sentences = _split_sentences(normalized_text)
    norm_time = time.time() - norm_start
    print(f"Normalization took {norm_time:.2f}s")

    spell_start = time.time()
    spell = SpellChecker()
    corrected_sentences = [
        _spell_correct_sentence(sentence, spell)
        for sentence in raw_sentences
        if sentence.strip()
    ]
    spell_time = time.time() - spell_start
    print(f"Spell correction took {spell_time:.2f}s")

    clean_script = " ".join(corrected_sentences).strip()
    text_chunks = _build_chunks(corrected_sentences, Config.TTS_CHUNK_WORDS)

    return {
        "text_chunks": text_chunks,
        "clean_script": clean_script,
        "page_count": page_count,
        "page_range": {"start": start_page, "end": end_page}
        if page_start is not None or page_end is not None
        else None,
        "word_count": len(clean_script.split()) if clean_script else 0,
    }
