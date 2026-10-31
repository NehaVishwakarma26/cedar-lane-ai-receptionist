"""JSON schemas Ollama shows the model. Descriptions tell it WHEN to use each tool."""
from config import SERVICES


# Builds one tool definition in the format Ollama expects.
def _tool_schema(name, description, properties, required):
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties, "required": required}}}


# Reusable argument definitions shared by several tools.
SERVICE_ARG = {"type": "string", "enum": list(SERVICES), "description": "Service key."}
DATE_ARG = {"type": "string", "description": "Date as YYYY-MM-DD (use the calendar in the system prompt)."}
TIME_ARG = {"type": "string", "description": "Time like 15:30 or 3:30 PM."}
PHONE_ARG = {"type": "string", "description": "Caller's phone number as they said it. Omit if already known."}

TOOLS = [
    _tool_schema(
        "check_availability",
        "Check whether a time is open, or list open start times for a day. ALWAYS use this before telling the "
        "caller a slot is open or full. If time is given, says AVAILABLE or NOT AVAILABLE and nearby alternatives.",
        {"service": SERVICE_ARG, "date": DATE_ARG,
         "time": {**TIME_ARG, "description": "Optional specific time to check."}},
        ["service", "date"]),
    _tool_schema(
        "book_appointment",
        "Create a booking. ONLY call after you have name, phone, service, date, time AND the caller confirmed "
        "the details you read back.",
        {"name": {"type": "string"}, "phone": PHONE_ARG, "service": SERVICE_ARG, "date": DATE_ARG,
         "time": TIME_ARG, "vehicle": {"type": "string", "description": "e.g. 2019 Honda Civic (optional)."}},
        ["name", "service", "date", "time"]),
    _tool_schema(
        "find_appointments",
        "List the caller's upcoming appointments (with event_id). Use before rescheduling, cancelling, or "
        "noting lateness.",
        {"phone": PHONE_ARG}, []),
    _tool_schema(
        "reschedule",
        "Move one of the caller's appointments to a new date/time. Needs event_id from find_appointments and "
        "caller confirmation.",
        {"event_id": {"type": "string"}, "phone": PHONE_ARG, "new_date": DATE_ARG, "new_time": TIME_ARG},
        ["event_id", "new_date", "new_time"]),
    _tool_schema(
        "cancel",
        "Cancel one of the caller's appointments. Needs event_id and caller confirmation.",
        {"event_id": {"type": "string"}, "phone": PHONE_ARG}, ["event_id"]),
    _tool_schema(
        "note_running_late",
        "Record that the caller is running late for today's appointment. Follow the tool's instruction in its reply.",
        {"minutes": {"type": "integer", "description": "How many minutes late."},
         "event_id": {"type": "string", "description": "Optional."}, "phone": PHONE_ARG},
        ["minutes"]),
    _tool_schema(
        "get_info",
        "Get official pricing, hours, prep requirements, vehicle rules or policies. Never state these from memory.",
        {"topic": {"type": "string", "enum": ["pricing", "hours", "prep", "vehicles", "policies"]}},
        ["topic"]),
    _tool_schema(
        "check_vehicle",
        "Check whether we detail a vehicle type. Pass the body type (sedan, suv, truck, motorcycle, rv, boat...). "
        "If you are confident which body type a make/model is, pass that type; otherwise pass what the caller said.",
        {"vehicle_type": {"type": "string"}}, ["vehicle_type"]),
    _tool_schema(
        "handoff_to_human",
        "Pass the caller to a human. Use for charge disputes, refunds, damage claims, angry callers, questions "
        "the tools can't answer, unsure vehicles, unverifiable appointments, or if the caller asks for a person.",
        {"reason": {"type": "string", "description": "One short sentence."},
         "category": {"type": "string", "enum": ["complaint", "other", "vehicle_check", "reschedule", "cancel"]}},
        ["reason"]),
]