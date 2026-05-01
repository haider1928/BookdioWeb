import re

import fitz


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(?<=\w)-\n(?=\w)", "", text)

    cleaned_lines = []
    blank_seen = False
    for line in text.split("\n"):
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            if not blank_seen:
                cleaned_lines.append("")
            blank_seen = True
            continue
        cleaned_lines.append(line)
        blank_seen = False

    cleaned = "\n".join(cleaned_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def extract_pdf_text(pdf_bytes: bytes) -> dict:
    if not pdf_bytes:
        raise ValueError("The uploaded PDF is empty.")

    try:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise ValueError("Invalid or corrupted PDF file.") from exc

    try:
        page_texts = []
        for page in document:
            page_text = clean_text(page.get_text("text"))
            if page_text:
                page_texts.append(page_text)

        return {
            "text": "\n\n".join(page_texts).strip(),
            "page_count": document.page_count,
        }
    finally:
        document.close()
