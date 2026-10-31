"""Availability tool backed by configured business hours and Google Calendar."""
from datetime import datetime, time, timedelta

import gcal
import slots
import utils
from config import GRANULARITY, HOURS, POLICIES, SERVICES, TZ
from utils import fmt_date, fmt_time

from .helpers import (
    ToolError,
    combine_date_and_time,
    format_start_times,
    parse_date_arg,
    parse_service_key,
    parse_time_arg,
    record_in_call_state,
)

LOOKAHEAD_DAYS = 14


def check_availability(args, session):
    """Check a requested service/time or list verified openings for a date."""
    service = parse_service_key(args)
    day = parse_date_arg(args)
    service_info = SERVICES[service]
    service_name = service_info["label"]
    duration = service_info["duration_min"]
    now = utils.now_local()

    if day < now.date():
        raise ToolError("That date is in the past.")

    requested_time = parse_time_arg(args) if args.get("time") else None
    query_start = datetime.combine(day, time.min, tzinfo=TZ)
    query_end = query_start + timedelta(days=LOOKAHEAD_DAYS + 1)
    busy = gcal.busy_intervals(query_start, query_end)
    record_in_call_state(session, "booking", f"Checked availability: {service_name} on {fmt_date(day)}")

    def starts_on(date_to_check):
        return slots.free_starts(
            date_to_check, duration, busy, HOURS, TZ, now, POLICIES, GRANULARITY
        )

    closed = slots.open_close(day, HOURS, TZ) is None
    day_starts = [] if closed else starts_on(day)
    requested_start = None

    if closed:
        reason = f"The shop is closed on {day:%A}s."
    elif requested_time is not None:
        requested_start = combine_date_and_time(day, requested_time)
        available, reason = slots.is_slot_free(
            requested_start, duration, busy, HOURS, TZ, now, POLICIES, GRANULARITY
        )
        if available:
            return f"AVAILABLE: {service_name} at {fmt_time(requested_start)} on {fmt_date(day)} is open."
        reason = f"NOT AVAILABLE at {fmt_time(requested_start)}: {reason}"
    else:
        reason = None

    if day_starts:
        if requested_start is not None:
            nearest = sorted(
                sorted(day_starts, key=lambda start: abs((start - requested_start).total_seconds()))[:3]
            )
            return (
                f"{reason} Nearest open start times for {service_name} on {fmt_date(day)}: "
                f"{format_start_times(nearest)}."
            )
        return (
            f"Open start times for {service_name} ({duration} min) on {fmt_date(day)}: "
            f"{format_start_times(day_starts)}. Shop local time."
        )

    prefix = reason or f"No openings for {service_name} on {fmt_date(day)}."
    for offset in range(1, LOOKAHEAD_DAYS + 1):
        next_day = day + timedelta(days=offset)
        next_starts = starts_on(next_day)
        if next_starts:
            return f"{prefix} Next availability: {fmt_date(next_day)}: {format_start_times(next_starts[:4])}."

    return f"{prefix} No openings in the next {LOOKAHEAD_DAYS} days. Offer handoff_to_human."
