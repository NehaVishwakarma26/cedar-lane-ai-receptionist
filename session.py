from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CallState:
    """What happened on this call; used for logging in code (not left to the LLM)."""
    category: Optional[str] = None
    outcome: Optional[str] = None
    event_id: Optional[str] = None
    handoff_reason: Optional[str] = None
    name: Optional[str] = None
    vehicle: Optional[str] = None
    phone: Optional[str] = None          # last phone used in a tool call (chat mode)
    needs_followup: bool = False
    summary_parts: list = field(default_factory=list)


@dataclass
class Session:
    session_id: str
    caller_phone: Optional[str] = None   # set by Vapi (voice); authoritative when present
    messages: list = field(default_factory=list)
    state: CallState = field(default_factory=CallState)
