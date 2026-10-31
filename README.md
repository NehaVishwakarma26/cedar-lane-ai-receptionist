# ProcIndex AI Receptionist

## Start the app (Windows PowerShell)

Install the project dependencies once:

```powershell
uv sync
```

Start the FastAPI backend in the first terminal:

```powershell
uv run uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Start the Streamlit chat in a second terminal:

```powershell
uv run streamlit run phase-1-chat/app.py
```

Open the local URL Streamlit prints (usually `http://localhost:8501`). The sidebar's
Backend URL defaults to `http://127.0.0.1:8000`; change it if the API is running elsewhere.
The UI stores display messages in the browser session and sends each new message with a
stable session ID. The backend keeps the actual conversation state.
After every chat reply, the backend saves or refreshes the contact and call-log rows. The
session ID makes these writes idempotent, so the sheet has one call-log row per conversation
and closing the browser tab does not discard the last successfully saved turn. If a Sheets
write fails, the UI reports it and the next message retries the save. Clicking **Start a new
conversation** also finalizes the session before discarding it.
Contacts without a phone number are keyed by chat session ID. After this change, update the
Contacts header in the configured spreadsheet by running `uv run python scripts/setup_sheets.py`.

## Before use

- Set `GEMINI_API_KEY` in `.env`. You can optionally set `GEMINI_MODEL`; the default is
  `gemini-3.8-flash`.
- Configure the Google service account and Calendar/Sheets access before testing tools that
  use those services.

The Streamlit UI does not decide that an appointment was booked. It displays the reply
from `/chat`; booking authorization and tool execution remain in the backend.
