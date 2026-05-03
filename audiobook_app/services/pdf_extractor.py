import re

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


def extract_pdf_text(pdf_bytes: bytes) -> dict:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page_count = doc.page_count
    raw_text = "".join(f"{page.get_text()}\n" for page in doc)
    doc.close()

    normalized_text = normalize_text(raw_text)
    raw_sentences = _split_sentences(normalized_text)

    spell = SpellChecker()
    corrected_sentences = [
        _spell_correct_sentence(sentence, spell)
        for sentence in raw_sentences
        if sentence.strip()
    ]

    clean_script = " ".join(corrected_sentences).strip()
    text_chunks = _build_chunks(corrected_sentences, Config.TTS_CHUNK_WORDS)

    return {
        "text_chunks": text_chunks,
        "clean_script": clean_script,
        "page_count": page_count,
        "word_count": len(clean_script.split()) if clean_script else 0,
    }
