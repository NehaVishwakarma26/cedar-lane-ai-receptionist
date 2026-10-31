"""Vapi webhook tests with mocked tools and Sheets writes."""

import main
import vapi_integration
from fastapi.testclient import TestClient


def test_vapi_tool_call_uses_call_session_and_deduplicates_retries(monkeypatch):
    vapi_integration.agent.SESSIONS.clear()
    executions = []
    monkeypatch.setattr(
        vapi_integration,
        "execute",
        lambda name, args, session: executions.append((name, args, session.session_id)) or "AVAILABLE",
    )
    message = {
        "type": "tool-calls",
        "call": {"id": "vapi-call-1", "customer": {"number": "+919876543210"}},
        "toolCallList": [{
            "id": "tool-call-1",
            "type": "function",
            "function": {"name": "check_availability", "arguments": {"service": "interior_detail", "date": "2026-11-05"}},
        }],
    }

    first = vapi_integration.handle_tool_calls(message)
    second = vapi_integration.handle_tool_calls(message)

    assert first == {"results": [{"name": "check_availability", "toolCallId": "tool-call-1", "result": "AVAILABLE"}]}
    assert second == first
    assert executions == [("check_availability", {"service": "interior_detail", "date": "2026-11-05"}, "vapi-call-1")]
    assert vapi_integration.agent.SESSIONS["vapi-call-1"].caller_phone == "+919876543210"


def test_vapi_end_of_call_saves_transcript_and_contact(monkeypatch):
    vapi_integration.agent.SESSIONS.clear()
    ended = []
    monkeypatch.setattr(vapi_integration.agent, "end_session", lambda session_id: ended.append(session_id) or True)
    message = {
        "type": "end-of-call-report",
        "call": {"id": "vapi-call-2", "customer": {"number": "+919876543210"}},
        "endedReason": "customer-ended-call",
        "artifact": {"transcript": "User: What are your hours? Assistant: I can check that."},
    }

    result = vapi_integration.handle_end_of_call(message)
    session = vapi_integration.agent.SESSIONS["vapi-call-2"]

    assert result == {"received": True, "saved_to_sheets": True}
    assert ended == ["vapi-call-2"]
    assert session.state.phone == "+919876543210"
    assert session.state.category == "other"
    assert session.state.summary_parts == [message["artifact"]["transcript"]]


def test_vapi_webhook_requires_configured_bearer_token(monkeypatch):
    monkeypatch.setattr(main.config, "VAPI_WEBHOOK_TOKEN", "test-secret")
    monkeypatch.setattr(main.vapi_integration, "handle_webhook", lambda payload: {"received": True})
    client = TestClient(main.app)

    unauthorized = client.post("/vapi/webhook", json={"message": {"type": "tool-calls"}})
    authorized = client.post(
        "/vapi/webhook",
        json={"message": {"type": "tool-calls"}},
        headers={"Authorization": "Bearer test-secret"},
    )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert authorized.json() == {"received": True}
