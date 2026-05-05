# PDF to Audiobook Web App

A Flask web app that extracts text from PDFs with PyMuPDF and converts it to MP3 audiobook audio with EdgeTTS. Also supports video generation with karaoke-style text rendering.

## Features

- Drag and drop PDF upload
- Clean page-by-page PDF text extraction with unicode normalization
- Dynamic English voice list from `edge_tts.list_voices()`
- Voice dropdown grouped by gender
- Speed control from `-50%` to `+50%`
- Font size slider (24-120px) for video output
- Font family selector with preview
- Spell checker with custom corrections + optional AI transformer (DistilBERT) for gibberish words
- Two-word merge patterns for PDF extraction artifacts (e.g., "the rre" → "There")
- IPA/ligature character fixes (50+ mappings)
- Video generation with optimized rendering (font caching, pre-calculation)
- Clean glow effect for active text in video
- Preview and download use aligned timing (no sync offset)
- Chunked MP3/Video generation
- Real-time preview playback after the first generated chunks
- Early MP3 download while the file is still being written
- EdgeTTS timeout and retry handling per chunk
- TTS workers: 6 concurrent for faster processing
- Background cleanup for output files older than 1 hour
- CORS enabled globally

## Project Structure

```text
audiobook_app/
|-- app.py              # Flask app entry point
|-- config.py           # Configuration settings
|-- requirements.txt    # Python dependencies
|-- routes/             # API endpoints
|   |-- upload.py       # PDF upload
|   |-- extract.py      # Text extraction
|   |-- convert.py      # TTS/Video conversion
|   |-- voices.py       # List EdgeTTS voices
|   |-- status.py       # Job status polling
|   |-- preview.py      # Audio/Video preview
|   |-- download.py    # Download final output
|   |-- subtitles.py   # Subtitle generation
|   `-- cleanup.py     # File cleanup
|-- services/
|   |-- pdf_extractor.py    # PDF text extraction + spell check
|   |-- tts_engine.py      # EdgeTTS wrapper
|   |-- job_manager.py     # Job queue management
|   |-- extraction_manager.py
|   |-- captioning.py      # Caption generation
|   `-- cleanup.py         # Background cleanup
|-- static/
|   |-- index.html         # Main UI
|   |-- css/               # Stylesheets
|   |-- js/                # Frontend scripts
|   `-- fonts/             # Font files
|-- outputs/              # Generated audio/video
`-- pdf_uploads/          # Uploaded PDFs
```

## Windows Setup

Use Python 3.10 or newer.

Python 3.13 note: use `PyMuPDF>=1.25.0`. Older PyMuPDF releases can fail to build from source on Python 3.13, especially with Microsoft Store Python installs where the `py` launcher is missing. This project pins `PyMuPDF==1.25.5`.

```powershell
cd E:\PROGRAMMING\BookdioWeb\audiobook_app
py -3.10 -m venv .venv
\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

If `py` is not available:

```powershell
python -m venv .venv
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Optional: AI Spell Checker

The spell checker supports an optional AI transformer for correcting gibberish/unknown words. To enable:

1. Install torch and transformers (already in requirements.txt)
2. In `audiobook_app/config.py`, set `SPELL_CHECK_TRANSFORMER = True`
3. Or use the "Use AI transformer" checkbox in the web UI

First run will download the DistilBERT model (~250MB). Subsequent runs use cached model.

## Run

The app runs on port `5000`.

Open:

```text
http://127.0.0.1:5000/
```

## API Format

Successful JSON routes return:

```json
{"success": true, "data": {}}
```

Failed JSON routes return:

```json
{"success": false, "error": "Message"}
```

`GET /download/<job_id>` returns the MP3 stream directly on success and JSON errors on failure.

## API Endpoints

- `POST /upload`: upload a PDF and receive extracted text plus page count.
- `GET /voices`: list English EdgeTTS voices grouped by gender.
- `POST /convert`: start a chunked conversion job and receive a `job_id`.
- `GET /status/<job_id>`: poll `status`, `chunks_done`, `chunks_total`, `preview_ready`, and `error`.
- `GET /preview/<job_id>`: serve the currently available partial MP3 with `Content-Type: audio/mpeg`.
- `GET /download/<job_id>`: stream the MP3 as it grows, then finish when the job completes.

## Streaming Behavior

The app splits extracted text into roughly 500-word chunks. EdgeTTS processes chunks sequentially and appends each generated chunk to one growing MP3 file. The UI polls `/status/<job_id>` and reveals playback plus download as soon as preview chunks are ready.

Each EdgeTTS chunk is wrapped in `asyncio.wait_for()` with a 30-second timeout and up to 2 retries. If EdgeTTS times out or fails after retries, the job status becomes `error`, and the frontend shows the error with a retry button.

## Async and Flask Notes

`edge-tts` is async. This app keeps Flask routes synchronous and calls the async EdgeTTS functions through service wrappers that use `asyncio.run()`.

That works with Flask's built-in development server and normal WSGI usage. Do not convert these route functions to `async def` while keeping `asyncio.run()` in the request path, because that can create a nested event loop error.

If you later move to async Flask views or ASGI, replace the sync wrappers with direct `await` calls.

EdgeTTS requires internet access because it contacts Microsoft's online text-to-speech service.
