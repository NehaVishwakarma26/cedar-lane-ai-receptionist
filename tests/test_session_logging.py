"""Chat-session logging tests; all Sheets calls are mocked."""

import agent
import main
from session import Session
from fastapi.testclient import TestClient


def _session(session_id="chat-test"):
    session = Session(session_id)
    session.messages.append({"role": "user", "content": "Hi"})
    session.state.name = "A Customer"
    session.state.phone = "+919876543210"
    session.state.category = "booking"
    session.state.outcome = "booked"
    session.state.summary_parts.append("Booked interior detailing")
    return session


def test_end_session_saves_contact_and_call_log_once(monkeypatch):
    agent.SESSIONS.clear()
    session = _session()
    agent.SESSIONS[session.session_id] = session
    contacts = []
    logs = []
    monkeypatch.setattr(agent.sheets, "upsert_contact", lambda *args, **kwargs: contacts.append((args, kwargs)))
    monkeypatch.setattr(agent.sheets, "append_call_log", lambda *args: logs.append(args))

    assert agent.end_session(session.session_id) is True
    assert session.session_id not in agent.SESSIONS
    assert len(contacts) == 1
    assert len(logs) == 1
    assert logs[0][1:7] == (
        "chat-test", "+919876543210", "A Customer", "booking",
        "Booked interior detailing", "booked",
    )


def test_end_session_can_retry_failed_sheet_log_without_duplicate_contact(monkeypatch):
    agent.SESSIONS.clear()
    session = _session("retry-test")
    agent.SESSIONS[session.session_id] = session
    contacts = []
    logs = []
    attempts = []

    def append_log(*args):
        attempts.append(args)
        if len(attempts) == 1:
            raise RuntimeError("temporary Sheets error")
        logs.append(args)

    monkeypatch.setattr(agent.sheets, "upsert_contact", lambda *args, **kwargs: contacts.append((args, kwargs)))
    monkeypatch.setattr(agent.sheets, "append_call_log", append_log)

    assert agent.end_session(session.session_id) is False
    assert session.session_id in agent.SESSIONS
    assert agent.end_session(session.session_id) is True
    assert session.session_id not in agent.SESSIONS
    assert len(contacts) == 1
    assert len(logs) == 1


def test_anonymous_chat_is_saved_as_contact_by_session_id(monkeypatch):
    agent.SESSIONS.clear()
    session = _session("anonymous-test")
    session.state.phone = None
    agent.SESSIONS[session.session_id] = session
    contacts = []
    monkeypatch.setattr(agent.sheets, "upsert_contact", lambda *args, **kwargs: contacts.append((args, kwargs)))
    monkeypatch.setattr(agent.sheets, "append_call_log", lambda *args: None)

    assert agent.end_session(session.session_id) is True
    assert len(contacts) == 1
    assert contacts[0][0][0] is None
    assert contacts[0][1]["session_id"] == "anonymous-test"


def test_end_session_api_endpoint(monkeypatch):
    monkeypatch.setattr(main.agent, "end_session", lambda session_id: True)
    response = TestClient(main.app).post("/sessions/ui-session/end")

    assert response.status_code == 200
    assert response.json() == {"session_id": "ui-session", "logged": True}


def test_chat_endpoint_saves_sheets_before_returning(monkeypatch):
    monkeypatch.setattr(main.agent, "respond", lambda session_id, message: "Hello")
    saved = []
    monkeypatch.setattr(main.agent, "save_session", lambda session_id: saved.append(session_id) or True)

    response = TestClient(main.app).post(
        "/chat", json={"session_id": "chat-session", "message": "Hi"}
    )

    assert response.status_code == 200
    assert response.json() == {
        "session_id": "chat-session",
        "reply": "Hello",
        "saved_to_sheets": True,
    }
    assert saved == ["chat-session"]
