"""Streamlit chat client for the FastAPI receptionist backend."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

import streamlit as st


DEFAULT_BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
REQUEST_TIMEOUT_SECONDS = 90


def post_chat(backend_url: str, session_id: str, message: str) -> tuple[str, bool]:
    """Send one message and return its reply and Sheets-save status."""
    payload = json.dumps({"session_id": session_id, "message": message}).encode("utf-8")
    request = Request(
        f"{backend_url.rstrip('/')}/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
            detail = body.get("detail", "The backend returned an error.")
        except (json.JSONDecodeError, UnicodeDecodeError):
            detail = "The backend returned an error."
        raise RuntimeError(f"Backend error ({exc.code}): {detail}") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError(
            "Could not reach the receptionist backend. Check that FastAPI is running "
            "and that the Backend URL is correct."
        ) from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RuntimeError("The backend returned an invalid response.") from exc

    reply = result.get("reply")
    if result.get("session_id") != session_id or not isinstance(reply, str) or not reply:
        raise RuntimeError("The backend response was missing the expected session or reply.")
    return reply, result.get("saved_to_sheets") is True


def end_chat_session(backend_url: str, session_id: str) -> None:
    """Ask the backend to save the call log before discarding a chat session."""
    request = Request(
        f"{backend_url.rstrip('/')}/sessions/{session_id}/end",
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
            detail = body.get("detail", "The backend returned an error.")
        except (json.JSONDecodeError, UnicodeDecodeError):
            detail = "The backend returned an error."
        raise RuntimeError(f"Backend error ({exc.code}): {detail}") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError("Could not reach the backend to save this call log.") from exc
    if result.get("session_id") != session_id or result.get("logged") is not True:
        raise RuntimeError("The backend did not confirm that this call log was saved.")


st.set_page_config(page_title="Cedar Lane Auto Detailing", page_icon="🚘", layout="centered")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.title("Cedar Lane")
    backend_url = st.text_input("Backend URL", value=DEFAULT_BACKEND_URL).strip()
    if st.button("Start a new conversation", use_container_width=True):
        if not st.session_state.messages:
            st.session_state.session_id = str(uuid4())
            st.session_state.messages = []
            st.rerun()
        else:
            with st.spinner("Saving this conversation…"):
                try:
                    end_chat_session(backend_url, st.session_state.session_id)
                except RuntimeError as exc:
                    st.error(str(exc))
                else:
                    st.session_state.session_id = str(uuid4())
                    st.session_state.messages = []
                    st.rerun()
    st.caption("Each conversation uses a new backend session.")

st.title("🚘 Cedar Lane Auto Detailing")
st.caption("Ask about services or request an appointment.")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt = st.chat_input("Ask a question or request an appointment…")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("The receptionist is responding…"):
            try:
                    reply, saved_to_sheets = post_chat(backend_url, st.session_state.session_id, prompt)
            except RuntimeError as exc:
                st.error(str(exc))
            else:
                st.markdown(reply)
                if not saved_to_sheets:
                    st.warning("This conversation could not be saved to Google Sheets yet. It will retry on your next message.")
                st.session_state.messages.append({"role": "assistant", "content": reply})
