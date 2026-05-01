# PDF to Audiobook Web App

A professional Flask project that turns uploaded PDF files into downloadable MP3 audiobooks. Text extraction is handled with PyMuPDF, and speech synthesis is handled with `edge-tts`.

## Features

- PDF upload with drag and drop
- Clean page-by-page text extraction
- Dynamic English voice list from `edge_tts.list_voices()`
- Voice dropdown grouped by gender
- Speed control from `-50%` to `+50%`
- MP3 generation into `audiobook_app/outputs`
- Audio player with play, pause, stop, seek, current time, total time, and download
- Collapsible extracted text preview
- Background cleanup for MP3 files older than 1 hour
- CORS enabled globally
- Consistent JSON API responses

## Project Structure

```text
audiobook_app/
├── app.py
├── config.py
├── requirements.txt
├── routes/
│   ├── __init__.py
│   ├── upload.py
│   ├── convert.py
│   ├── voices.py
│   └── download.py
├── services/
│   ├── __init__.py
│   ├── pdf_extractor.py
│   ├── tts_engine.py
│   └── cleanup.py
├── outputs/
└── static/
    ├── css/
    │   ├── main.css
    │   ├── player.css
    │   └── upload.css
    ├── js/
    │   ├── upload.js
    │   ├── voices.js
    │   ├── convert.js
    │   └── player.js
    └── index.html
```

## Windows Setup

Use Python 3.10 or newer.

```powershell
cd E:\PROGRAMMING\BookdioWeb\audiobook_app
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

If `py` is not available, use:

```powershell
python -m venv .venv
```

If PowerShell blocks activation, run:

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

`GET /download/<filename>` returns the MP3 file directly on success and JSON errors on failure.

## Async and Flask Notes

`edge-tts` is async. This app keeps Flask routes synchronous and calls the async `edge-tts` functions through service wrappers that use `asyncio.run()`.

This works with Flask's built-in development server and normal WSGI usage. Do not convert these Flask route functions to `async def` while keeping `asyncio.run()` inside the request path, because that can cause a nested event loop error.

If you later move to async Flask views or ASGI, replace the sync wrappers with direct `await` calls.

`edge-tts` requires internet access because it contacts Microsoft's online text-to-speech service.
