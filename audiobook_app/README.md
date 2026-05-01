# PDF to Audiobook

A Flask web app that extracts text from PDF files with PyMuPDF and converts the text to MP3 audio with `edge-tts`.

## Features

- Drag and drop PDF upload
- Clean page-by-page PDF text extraction
- Dynamic English voice list from `edge_tts.list_voices()`
- Speed control from `-50%` to `+50%`
- MP3 generation into the `outputs` folder
- Browser audio player with seek, play, pause, stop, and download controls
- Background cleanup for MP3 files older than 1 hour
- Consistent JSON API responses
- CORS enabled globally

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

If `py` is not available, create the environment with:

```powershell
python -m venv .venv
```

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Run

The app runs on port `5000`.

Open this URL in your browser:

```text
http://127.0.0.1:5000/
```

## API Response Format

Successful JSON routes return:

```json
{"success": true, "data": {}}
```

Failed JSON routes return:

```json
{"success": false, "error": "Message"}
```

The download route returns the MP3 file directly on success and JSON errors on failure.

## Async and Flask Notes

`edge-tts` is async. This app keeps Flask routes synchronous and calls the async `edge-tts` functions through `asyncio.run()` inside service wrappers.

That works correctly with Flask's built-in development server and normal WSGI usage. Do not change these route functions to `async def` while still calling `asyncio.run()`, because that can create a nested event loop error.

If you later move to async Flask views or an ASGI server, replace the sync wrappers with direct `await` calls.

`edge-tts` requires internet access because it contacts Microsoft's online text-to-speech service.
