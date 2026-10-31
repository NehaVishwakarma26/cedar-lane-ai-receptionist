from datetime import date, datetime, time, timedelta

import gcal
import utils
from config import SERVICES, TZ
from utils import fmt_time, normalize_phone


# Higher number means higher priority
CATEGORY_PRIORITY = {
    "other": 1,
    "pricing": 2,
    "hours": 2,
    "prep": 2,
    "vehicle_check": 3,
    "booking": 5,
    "reschedule": 5,
    "cancel": 5,
    "running_late": 5,
    "complaint": 6,
}


# Used when something goes wrong
class ToolError(Exception):
    pass


# Save the call category and summary
def record_in_call_state(session, category=None, summary=None):
    state = session.state

    if category:
        new_priority = CATEGORY_PRIORITY.get(category, 0)
        old_priority = CATEGORY_PRIORITY.get(state.category, 0)

        if new_priority >= old_priority:
            state.category = category

    if summary:
        state.summary_parts.append(summary)


# Save how the call ended
def set_call_outcome(session, outcome):
    if session.state.outcome != "handed_off":
        session.state.outcome = outcome


# Get and validate the caller's phone number
def resolve_caller_phone(session, args):
    phone = session.caller_phone or args.get("phone")

    if not phone:
        raise ToolError("Phone number is required.")

    phone = normalize_phone(str(phone))

    if not phone:
        raise ToolError("Invalid phone number.")

    session.state.phone = phone
    return phone


# Check whether the requested service exists
def parse_service_key(args):
    service = str(args.get("service", "")).strip().lower().replace(" ", "_")

    if service not in SERVICES:
        raise ToolError(
            f"Unknown service. Available services: {', '.join(SERVICES)}"
        )

    return service


# Convert a date string into a Python date
def parse_date_arg(args, arg_name="date"):
    try:
        return date.fromisoformat(str(args.get(arg_name, "")).strip())
    except ValueError:
        raise ToolError(f"{arg_name} must be in YYYY-MM-DD format.")


# Accepted time formats
ACCEPTED_TIME_FORMATS = [
    "%H:%M",
    "%I:%M %p",
    "%I:%M%p",
    "%I %p",
    "%I%p",
]


# Convert a time string into a Python time
def parse_time_arg(args, arg_name="time"):
    text = str(args.get(arg_name, "")).strip().upper()

    for time_format in ACCEPTED_TIME_FORMATS:
        try:
            return datetime.strptime(text, time_format).time()
        except ValueError:
            continue

    raise ToolError(f"{arg_name} must look like 15:30 or 3:30 PM.")


# Combine a date and time
def combine_date_and_time(day, time_of_day):
    return datetime.combine(day, time_of_day, tzinfo=TZ)


# Get busy time slots from Google Calendar for one day
def busy_intervals_for_day(day, exclude_event_id=None):
    start = datetime.combine(day, time.min, tzinfo=TZ)
    end = start + timedelta(days=1)

    return gcal.busy_intervals(start, end, exclude_event_id)


# Get private information stored in a calendar event
def private_properties(event):
    return event.get("extendedProperties", {}).get("private", {}) or {}


# Find and validate an appointment belonging to the caller
def load_callers_event(phone, event_id):
    if not event_id:
        raise ToolError("Appointment ID is required. Find appointments first.")

    try:
        event = gcal.get_event(str(event_id))
    except Exception:
        event = None

    if not event:
        raise ToolError("Appointment not found.")

    if event.get("status") == "cancelled":
        raise ToolError("This appointment has been cancelled.")

    if private_properties(event).get("phone") != phone:
        raise ToolError("This appointment does not belong to this caller.")

    if gcal.event_end(event) <= utils.now_local():
        raise ToolError("This appointment is in the past.")

    return event


# Convert appointment times into readable text
def format_start_times(start_times):
    return ", ".join(fmt_time(t) for t in start_times)