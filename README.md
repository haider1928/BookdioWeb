# PDF to Audiobook Web App

A Flask web app that extracts text from PDFs with PyMuPDF and converts it to MP3 audiobook audio with EdgeTTS.

## Features

- Drag and drop PDF upload
- Clean page-by-page PDF text extraction
- Dynamic English voice list from `edge_tts.list_voices()`
- Voice dropdown grouped by gender
- Speed control from `-50%` to `+50%`
- Normal speed bug fixed by always sending `+0%` to EdgeTTS
- Chunked MP3 generation into `audiobook_app/outputs`
- Real-time preview playback after the first generated chunks
- Early MP3 download while the file is still being written
- EdgeTTS timeout and retry handling per chunk
- Background cleanup for MP3 files older than 1 hour
- CORS enabled globally

## Project Structure

```text
audiobook_app/
|-- app.py
|-- config.py
|-- requirements.txt
|-- routes/
|   |-- __init__.py
|   |-- upload.py
|   |-- convert.py
|   |-- voices.py
|   |-- status.py
|   |-- preview.py
|   `-- download.py
|-- services/
|   |-- __init__.py
|   |-- pdf_extractor.py
|   |-- tts_engine.py
|   |-- job_manager.py
|   `-- cleanup.py
|-- outputs/
`-- static/
    |-- css/
    |   |-- main.css
    |   |-- player.css
    |   `-- upload.css
    |-- js/
    |   |-- upload.js
    |   |-- voices.js
    |   |-- convert.js
    |   `-- player.js
    `-- index.html
```

## Windows Setup

Use Python 3.10 or newer.

Python 3.13 note: use `PyMuPDF>=1.25.0`. Older PyMuPDF releases can fail to build from source on Python 3.13, especially with Microsoft Store Python installs where the `py` launcher is missing. This project pins `PyMuPDF==1.25.5`.

```powershell
cd E:\PROGRAMMING\BookdioWeb\audiobook_app
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
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
