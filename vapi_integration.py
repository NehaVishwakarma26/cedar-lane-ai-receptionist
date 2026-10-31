"""Vapi server-webhook adapter for the receptionist's existing tool layer."""

import json
import logging

import agent
from tools import TOOLS, execute

log = logging.getLogger(__name__)


def _caller_phone(message, call):
    customer = message.get("customer") or call.get("customer") or {}
    phone_number = message.get("phoneNumber") or call.get("phoneNumber") or {}
    return customer.get("number") or phone_number.get("number")


def _call_session(message):
    call = message.get("call") or {}
    call_id = call.get("id") or message.get("callId")
    if not isinstance(call_id, str) or not call_id.strip():
        raise ValueError("Vapi message is missing call.id.")
    session = agent.get_session(call_id, _caller_phone(message, call))
    if not any(item.get("role") == "user" for item in session.messages):
        session.messages.append({"role": "user", "content": "Vapi voice call"})
    return session, call


def _tool_calls(message):
    calls = message.get("toolCallList")
    if calls is None:
        calls = [item.get("toolCall", {}) for item in message.get("toolWithToolCallList", [])]
    return calls if isinstance(calls, list) else []


def _arguments(value):
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise ValueError("Tool arguments must be a JSON object.")
    return value


def handle_tool_calls(message):
    """Execute Vapi function calls against the existing local allowlist."""
    session, _ = _call_session(message)
    results = []
    allowed_names = {schema["function"]["name"] for schema in TOOLS}

    for item in _tool_calls(message):
        function = item.get("function") or {}
        call_id = item.get("id") or item.get("toolCallId")
        name = function.get("name")
        if not isinstance(call_id, str) or not call_id:
            results.append({"name": str(name or "unknown"), "toolCallId": "", "error": "Missing tool call ID."})
            continue
        cached = session.vapi_tool_results.get(call_id)
        if cached is not None:
            results.append(cached)
            continue
        if name not in allowed_names:
            result = {"name": str(name or "unknown"), "toolCallId": call_id,
                      "error": "That action is not supported."}
        else:
            try:
                args = _arguments(function.get("arguments", {}))
                output = execute(name, args, session)
                log.info("Vapi tool %s executed for call %s", name, session.session_id)
                result = {"name": name, "toolCallId": call_id, "result": str(output)}
            except (ValueError, json.JSONDecodeError):
                result = {"name": name, "toolCallId": call_id,
                          "error": "The tool arguments were invalid. Please ask the caller to clarify."}
            except Exception:
                log.exception("Vapi tool %s failed for call %s", name, session.session_id)
                result = {"name": name, "toolCallId": call_id,
                          "error": "The action could not be completed. Please offer staff follow-up."}
        session.vapi_tool_results[call_id] = result
        results.append(result)
    return {"results": results}


def handle_end_of_call(message):
    """Capture Vapi's final transcript and persist the voice interaction."""
    session, call = _call_session(message)
    artifact = message.get("artifact") or {}
    transcript = artifact.get("transcript") or message.get("transcript") or ""
    summary = message.get("summary") or artifact.get("summary") or ""
    if transcript:
        session.messages.append({"role": "user", "content": str(transcript)[:12000]})
    if summary:
        session.state.summary_parts.append(str(summary)[:2000])
    elif transcript and not session.state.summary_parts:
        session.state.summary_parts.append(str(transcript)[:2000])
    if not session.state.category:
        session.state.category = "other"
    if not session.state.outcome:
        session.state.outcome = "completed"
    if not session.state.phone:
        session.state.phone = session.caller_phone

    saved = agent.end_session(session.session_id)
    if not saved:
        log.error("Vapi call %s ended but its Sheets records could not be saved", call.get("id"))
    return {"received": True, "saved_to_sheets": saved}


def handle_webhook(payload):
    """Dispatch the supported Vapi server-message types."""
    message = payload.get("message") if isinstance(payload, dict) else None
    if not isinstance(message, dict):
        raise ValueError("Expected a Vapi webhook with a message object.")
    event_type = message.get("type")
    if event_type == "tool-calls":
        return handle_tool_calls(message)
    if event_type == "end-of-call-report":
        return handle_end_of_call(message)
    # Other subscribed status/transcript events need no response or side effect.
    return {"received": True}
