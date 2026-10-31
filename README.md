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
stable session ID. The backend keeps the actual conversation state. Text chat saves the
session to Sheets when **Start a new conversation** is clicked; closing its browser tab alone
does not finalize the session. Phase 2 voice calls are saved from Vapi's end-of-call report.
Contacts without a phone number are keyed by chat session ID. After this change, update the
Contacts header in the configured spreadsheet by running `uv run python scripts/setup_sheets.py`.

## Before use

- Set `GEMINI_API_KEY` in `.env`. You can optionally set `GEMINI_MODEL`; the default is
  `gemini-3.8-flash`.
- Configure the Google service account and Calendar/Sheets access before testing tools that
  use those services.

The Streamlit UI does not decide that an appointment was booked. It displays the reply
from `/chat`; booking authorization and tool execution remain in the backend.

## Phase 2: Vapi voice assistant

The FastAPI app exposes `/vapi/webhook` for Vapi Function tool calls and end-of-call
reports. Function calls use the same allowlisted Python tools as Phase 1. Vapi call IDs
identify the backend session, caller ID is passed into the tool session when available,
and the end-of-call report saves the transcript and call outcome to Sheets.

### Configure Vapi

1. Copy `.env.example` to `.env` only if you need a reference; keep your real `.env` private.
   Set `VAPI_SERVER_URL` to your public HTTPS address ending in `/vapi/webhook`, and set
   `VAPI_WEBHOOK_TOKEN` to a long random value. Set `VAPI_CREDENTIAL_ID` after creating the
   matching Vapi credential.
2. Run the backend on a host Vapi can reach. For local testing, expose port 8000 through an
   HTTPS tunnel such as ngrok:

   ```powershell
   uv run uvicorn main:app --host 0.0.0.0 --port 8000
   ```

   In another terminal:

   ```powershell
   ngrok http 8000
   ```

   Put the tunnel's HTTPS URL plus `/vapi/webhook` in `VAPI_SERVER_URL`. Restart FastAPI
   after changing `.env`.
3. In Vapi's Integrations, add your Google Gemini API key. The local `GEMINI_API_KEY` is not
   automatically shared with Vapi.
4. In Vapi's server credentials, create a Bearer credential whose token value matches
   `VAPI_WEBHOOK_TOKEN`; use the returned credential ID as `VAPI_CREDENTIAL_ID`.
5. Generate the assistant configuration reference:

   ```powershell
   uv run python scripts/export_vapi_assistant.py --output vapi_assistant.json
   ```

   Use its model, prompt, tool schemas, transcriber, voice, and server settings when creating
   the assistant in Vapi. Configure its server messages to include `tool-calls` and
   `end-of-call-report`, then attach a Vapi phone number or start a web call.

The generated configuration selects Google Gemini 3.8 Flash, Deepgram Nova 3 transcription,
and Vapi's Elliot voice. These can be changed in the Vapi dashboard after testing. Vapi must
be publicly reachable over HTTPS for webhooks. A real Vapi call still needs to be made from
your Vapi account; no live call or live Calendar/Sheets operation was run during development.
