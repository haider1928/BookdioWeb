import re
import time
import unicodedata
from pathlib import Path
from typing import Callable, Any
from collections import Counter
import fitz  # PyMuPDF
from spellchecker import SpellChecker
from config import Config
import torch

_spell_checker: SpellChecker | None = None
_transformer_model = None
_transformer_tokenizer = None
_transformer_cache: dict = {}

TRANSFORMER_MODEL_NAME = "distilbert-base-uncased"


def _use_transformer() -> bool:
    """Check if transformer-based spell correction is enabled."""
    return Config.SPELL_CHECK_TRANSFORMER

# Custom mapping for commonly corrupted words
_CUSTOM_CORRECTIONS = {
    "justires": "justifies",
    "justies": "justifies",
    "rre": "there",
    "thee": "the",
    "filed": "filed",  # keep as-is
    "dignires": "dignifies",
    "signires": "signifies",
    "justifes": "justifies",
    "justifis": "justifies",
    "magifes": "magnifies",
    "certes": "certifies",
    "identifes": "identifies",
    "rr": "are",
    "theer": "there",
    "thier": "their",
    "their": "their",
}

# Patterns where two words should be merged (e.g., "the rre" -> "There")
_MERGE_PATTERNS = {
    ("the", "rre"): "There",
    ("the", "rr"): "There",
    ("a", "lso"): "Also",
    ("an", "d"): "and",  # "an d" -> "and"
    ("i", "t"): "it",      # "i t" -> "it"
    ("t", "here"): "There", # "t here" -> "There"
}

# Ligature and IPA character fixes
_LIGATURE_FIXES = {
    # Ligatures
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",

    # Smart quotes and dashes
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2013": "-",
    "\u2014": "-",
    "\u2026": "...",
    "\u2022": "-",
    "\u2027": "-",

    # IPA characters that appear as gibberish in PDF extraction
    "\u0279": "r",    # Turned small r -> r
    "\u027b": "r",    # Turned small r with hook -> r
    "\u0280": "r",    # Small capital R -> r
    "\u027e": "r",    # Turned small r with long leg -> r
    "\u0283": "sh",   # Esh -> sh
    "\u0282": "s",    # Small s with hook -> s
    "\u0288": "t",    # Small t with retroflex hook -> t
    "\u0256": "d",    # Small d with retroflex hook -> d
    "\u0258": "e",    # Small reversed epsilon -> e
    "\u025b": "e",    # Small open epsilon -> e
    "\u025c": "e",    # Small reversed open e -> e
    "\u0259": "e",    # Schwa -> e
    "\u025a": "e",    # Small schwa with hook -> e
    "\u028c": "u",    # Small turned v -> u
    "\u028a": "u",    # Small upsilon -> u
    "\u026a": "i",    # Small capital I -> i
    "\u0268": "i",    # Small i with stroke -> i
    "\u026f": "m",    # Small turned m -> m
    "\u0270": "m",    # Small long leg turned m -> m
    "\u0271": "n",    # Small n with left hook -> n
    "\u014b": "ng",   # Small eng -> ng
    "\u0261": "g",    # Small script g -> g
    "\u0264": "ae",   # Small ram's horn -> ae
    "\u00e6": "ae",   # Latin ae ligature
    "\u00f0": "d",    # Eth -> d
    "\u00fe": "th",   # Thorn -> th
    "\u0275": "o",    # Small barred o -> o
    "\u0254": "o",    # Small open o -> o
    "\u0252": "a",    # Small turned alpha -> a
    "\u0251": "a",    # Small alpha -> a
    "\u0284": "j",    # Small dotless j with stroke -> j
    "\u0292": "zh",   # Small ezh -> zh
    "\u02a4": "dz",   # Small dz digraph -> dz
    "\u02a7": "ch",   # Small tesh -> ch
    "\u02a5": "dz",   # Small dz digraph with retroflex hook -> dz
    "\u0273": "n",    # Small n with retroflex hook -> n
    "\u0274": "n",    # Small capital N -> n
    "\u029f": "l",    # Small capital L -> l
    "\u026b": "l",    # Small l with middle tilde -> l
    "\u026c": "l",    # Small l with belt -> l
    "\u028e": "y",    # Small turned y -> y
    "\u028b": "v",    # Small v with hook -> v
    "\u0295": "'",    # Glottal stop -> '
    "\u02c8": "'",    # Primary stress mark -> '
    "\u02cc": "'",    # Secondary stress mark -> '
    "\u02b0": "h",    # Modifier letter small h -> h
    "\u02b7": "w",    # Modifier letter small w -> w
    "\u02e4": "j",    # Modifier letter small j -> j
}


def _normalize_unicode_chars(text: str) -> str:
    """Fallback normalization: decompose unicode chars and convert to ASCII."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))

    remaining_fixes = {
        "\u00a0": " ",   # Non-breaking space
        "\u200b": "",    # Zero-width space
        "\ufeff": "",    # BOM
        "\u200e": "",    # Left-to-right mark
        "\u200f": "",    # Right-to-left mark
        "\u202a": "",    # Left-to-right embedding
        "\u202b": "",    # Right-to-left embedding
        "\u202c": "",    # Pop directional formatting
        "\u202d": "",    # Left-to-right override
        "\u202e": "",    # Right-to-left override
    }
    for ch, replacement in remaining_fixes.items():
        text = text.replace(ch, replacement)

    text = "".join(ch for ch in text if ord(ch) >= 32 or ch in "\n\r\t")
    return text


def _get_spell_checker() -> SpellChecker:
    global _spell_checker
    if _spell_checker is None:
        print("[PDF] Initializing SpellChecker dictionary...")
        _spell_checker = SpellChecker(distance=3)
    return _spell_checker


def _is_gibberish_word(word: str, spell: SpellChecker) -> bool:
    """Check if a word needs transformer correction (gibberish/unknown)."""
    word_lower = word.lower()
    if len(word_lower) <= 2:
        return False
    if word_lower in _CUSTOM_CORRECTIONS:
        return False
    if word.isdigit():
        return False
    vowels = set("aeiouAEIOU")
    if not any(ch in vowels for ch in word_lower):
        return True
    if len(word_lower) > 20:
        return True
    known = spell.known([word_lower])
    if not known:
        consonant_ratio = sum(1 for ch in word_lower if ch.isalpha() and ch not in vowels) / max(len(word_lower), 1)
        if consonant_ratio > 0.85 and len(word_lower) > 4:
            return True
    return False


def _load_transformer_model():
    global _transformer_model, _transformer_tokenizer
    if _transformer_model is None:
        try:
            from transformers import AutoModelForMaskedLM, AutoTokenizer
            print("[PDF] Loading transformer model (DistilBERT)...")
            _transformer_tokenizer = AutoTokenizer.from_pretrained(TRANSFORMER_MODEL_NAME)
            _transformer_model = AutoModelForMaskedLM.from_pretrained(TRANSFORMER_MODEL_NAME)
            _transformer_model.eval()
            print("[PDF] Transformer model loaded successfully.")
        except Exception as e:
            print(f"[PDF] Failed to load transformer model: {e}. Falling back to pyspellchecker only.")
            return False
    return True


def _transformer_correct(word: str, sentence: str, word_index: int) -> str | None:
    """Use transformer to correct a gibberish word in context."""
    global _transformer_cache
    if not _use_transformer():
        return None
    if not _load_transformer_model():
        return None
    cache_key = (word.lower(), sentence.lower(), word_index)
    if cache_key in _transformer_cache:
        return _transformer_cache[cache_key]
    try:
        words = sentence.split()
        if word_index < len(words):
            words[word_index] = "[MASK]"
            masked_sentence = " ".join(words)
            inputs = _transformer_tokenizer(masked_sentence, return_tensors="pt")
            with torch.no_grad():
                outputs = _transformer_model(**inputs)
            predictions = outputs.logits[0]
            mask_token_index = inputs.input_ids[0].tolist().index(_transformer_tokenizer.mask_token_id)
            top_tokens = torch.topk(predictions[mask_token_index], 5).indices.tolist()
            for token_id in top_tokens:
                candidate = _transformer_tokenizer.decode([token_id]).strip()
                if candidate and candidate.isalpha() and len(candidate) <= len(word) + 5:
                    if len(candidate) >= 2:
                        _transformer_cache[cache_key] = candidate
                        return candidate
        _transformer_cache[cache_key] = None
        return None
    except Exception as e:
        print(f"[PDF] Transformer correction error: {e}")
        return None


def normalize_text(text: str) -> str:
    """Clean OCR artifacts and normalize whitespace/punctuation."""
    for broken, fixed in _LIGATURE_FIXES.items():
        text = text.replace(broken, fixed)
    text = _normalize_unicode_chars(text)
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


def _score_candidate(candidate: str, original: str) -> float:
    """Score a candidate based on similarity to original word."""
    score = 0.0
    candidate_lower = candidate.lower()
    original_lower = original.lower()

    # Prefix match bonus (e.g., "justires" -> "justifies" shares "justi")
    prefix_len = 0
    for i in range(min(len(candidate_lower), len(original_lower))):
        if candidate_lower[i] == original_lower[i]:
            prefix_len += 1
        else:
            break
    score += prefix_len * 2.0

    # Suffix match bonus
    suffix_len = 0
    for i in range(1, min(len(candidate_lower), len(original_lower)) + 1):
        if candidate_lower[-i] == original_lower[-i]:
            suffix_len += 1
        else:
            break
    score += suffix_len * 1.0

    # Penalty for "fices" suffix when original has "fies"
    if original_lower.endswith("fies") and candidate_lower.endswith("fices"):
        score -= 5.0

    return score


def _spell_correct_sentence(sentence: str, spell: SpellChecker) -> str:
    words = sentence.split()
    merged_words = []
    i = 0

    # Pre-process: merge two-word patterns like "the rre" -> "There"
    while i < len(words):
        if i < len(words) - 1:
            pattern = (words[i].lower(), words[i + 1].lower())
            if pattern in _MERGE_PATTERNS:
                merged_words.append(_MERGE_PATTERNS[pattern])
                i += 2
                continue
        merged_words.append(words[i])
        i += 1

    words = merged_words
    corrected: list[str] = []

    for i, token in enumerate(words):
        match = re.match(r"^([\"'(\[]*)([A-Za-z][A-Za-z'-]*)([)\]\"'.,;:!?]*)$", token)
        if not match:
            corrected.append(token)
            continue

        prefix, core, suffix = match.groups()
        if _should_skip_spellcheck(core):
            corrected.append(token)
            continue

        core_lower = core.lower()
        suggestion = None

        # Check custom corrections first
        if core_lower in _CUSTOM_CORRECTIONS:
            suggestion = _CUSTOM_CORRECTIONS[core_lower]
        else:
            # Try pyspellchecker
            candidate = spell.correction(core_lower)
            if candidate and candidate != core_lower:
                suggestion = candidate

        # If no suggestion or same as original, check for gibberish and use transformer
        if (suggestion is None or suggestion == core_lower) and _is_gibberish_word(core_lower, spell):
            transformer_suggestion = _transformer_correct(core, sentence, i)
            if transformer_suggestion:
                suggestion = transformer_suggestion

        if suggestion and suggestion != core_lower:
            if core[0].isupper():
                suggestion = suggestion.capitalize()
            corrected.append(f"{prefix}{suggestion}{suffix}")
        else:
            corrected.append(token)

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
    progress_callback: Callable | None = None,
    spell_progress_callback: Callable | None = None,
    use_spell_check: bool = Config.SPELL_CHECK_ENABLED
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
    corrected_sentences = []
    total_sentences = len([s for s in raw_sentences if s.strip()])
    sentences_done = 0

    if use_spell_check and Config.SPELL_CHECK_ENABLED:
        spell = _get_spell_checker()
        for sentence in raw_sentences:
            if not sentence.strip():
                continue
            corrected = _spell_correct_sentence(sentence, spell)
            corrected_sentences.append(corrected)
            sentences_done += 1
            if spell_progress_callback:
                spell_progress_callback(sentences_done, total_sentences)
        spell_time = time.time() - spell_start
        print(f"[PDF] Spell check: {sentences_done} sentences in {spell_time:.2f}s")
    else:
        print(f"[PDF] Spell check skipped (disabled)")
        corrected_sentences = [s for s in raw_sentences if s.strip()]

    corrected_sentences = [s for s in corrected_sentences if s.strip()]

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
