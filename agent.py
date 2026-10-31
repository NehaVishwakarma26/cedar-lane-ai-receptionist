"""respond(session_id, text, caller_phone=None) -> str. UI-agnostic (chat.py / Vapi call it)."""
import logging

from google import genai
from google.genai import types

import config
import sheets
import utils
from prompts import build_system_prompt
from session import Session
from tools import TOOLS, execute
from utils import normalize_phone, strip_think

log = logging.getLogger(__name__)
SESSIONS = {}
MAX_STEPS = 6
_gemini_client = None
FALLBACK = ("I couldn't complete that request. I've recorded it for staff review, but this system "
            f"does not automatically notify the team. Please contact the shop at {config.SHOP['phone']}.")


def get_session(session_id, caller_phone=None):
    s = SESSIONS.get(session_id)
    if s is None:
        s = SESSIONS[session_id] = Session(session_id)
    if caller_phone and not s.caller_phone:
        s.caller_phone = normalize_phone(caller_phone)
    return s


def _get_gemini_client():
    """Create the Gemini client lazily so imports work without an API key."""
    global _gemini_client
    if not config.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured in the environment.")
    if _gemini_client is None:
        _gemini_client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _gemini_client


def _gemini_tools():
    """Translate the existing allowlisted Ollama schemas to Gemini declarations."""
    declarations = []
    for tool in TOOLS:
        function = tool["function"]
        declarations.append(types.FunctionDeclaration(
            name=function["name"],
            description=function["description"],
            parameters=function["parameters"],
        ))
    return [types.Tool(function_declarations=declarations)]


def _generate(session, system_prompt):
    """Ask Gemini for the next text response or a locally executed tool call."""
    response = _get_gemini_client().models.generate_content(
        model=config.GEMINI_MODEL,
        contents=session.model_contents,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=_gemini_tools(),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            temperature=0.2,
        ),
    )
    if not response.candidates or not response.candidates[0].content:
        raise RuntimeError("Gemini returned no usable response.")
    content = response.candidates[0].content
    # Preserve the original model response, including function-call metadata,
    # for the next turn in the Gemini conversation.
    session.model_contents.append(content)
    calls = [part.function_call for part in (content.parts or []) if part.function_call]
    text = "" if calls else (response.text or "")
    return content, calls, text


def respond(session_id, text, caller_phone=None):
    s = get_session(session_id, caller_phone)
    system_prompt = build_system_prompt(utils.now_local(), s.caller_phone)
    s.messages.append({"role": "user", "content": text})
    s.model_contents.append(types.Content(role="user", parts=[types.Part.from_text(text=text)]))

    for _ in range(MAX_STEPS):
        _, calls, content = _generate(s, system_prompt)
        if not calls:
            if content:
                reply = strip_think(content)
                s.messages.append({"role": "assistant", "content": reply})
                return reply
            raise RuntimeError("Gemini returned an empty response.")
        results = []
        for call in calls:
            arguments = dict(call.args or {})
            result = execute(call.name, arguments, s)
            log.info("tool %s(%s) -> %s", call.name, arguments, result)
            results.append(types.Part.from_function_response(
                name=call.name,
                response={"result": result},
            ))
        s.model_contents.append(types.Content(role="user", parts=results))

    st = s.state                                                # never got a final answer
    st.outcome, st.needs_followup = "handed_off", True
    st.handoff_reason = st.handoff_reason or "agent failed to produce a reply"
    s.messages.append({"role": "assistant", "content": FALLBACK})
    return FALLBACK


def end_session(session_id):
    """Log the call in CODE (don't rely on an 8B model to remember). Call on hangup/exit."""
    s = SESSIONS.pop(session_id, None)
    if s is None or not any(m["role"] == "user" for m in s.messages):
        return
    st = s.state
    phone = s.caller_phone or st.phone
    category = st.category or "other"
    outcome = st.outcome or ("resolved" if st.category else "abandoned")
    summary = "; ".join(st.summary_parts) or "No actions taken"
    now = utils.now_local()
    if phone:
        try:
            sheets.upsert_contact(phone, st.name, st.vehicle, category, summary, st.needs_followup, now)
        except Exception:
            log.exception("failed to upsert contact for call %s", session_id)

    try:
        sheets.append_call_log(now.isoformat(timespec="seconds"), s.session_id, phone, st.name, category,
                               summary, outcome, st.event_id, st.handoff_reason)
    except Exception:
        log.exception("failed to append call log for call %s", session_id)
