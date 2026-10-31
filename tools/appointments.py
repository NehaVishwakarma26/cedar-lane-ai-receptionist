"""Tools for booking, finding, rescheduling, and cancelling appointments."""

from datetime import timedelta

import gcal
import slots
import utils

from config import GRANULARITY, HOURS, POLICIES, SERVICES, TZ
from utils import fmt_human, fmt_time

from .helpers import (
    ToolError,
    busy_intervals_for_day,
    combine_date_and_time,
    load_callers_event,
    parse_date_arg,
    parse_service_key,
    parse_time_arg,
    private_properties,
    record_in_call_state,
    resolve_caller_phone,
    set_call_outcome,
)


def book_appointment(args, session):
    # 1. Get and validate customer details
    name = str(args.get("name", "")).strip()

    if len(name) < 2:
        raise ToolError("The caller's name is required.")

    phone = resolve_caller_phone(session, args)
    service = parse_service_key(args)
    date = parse_date_arg(args)
    time = parse_time_arg(args)

    vehicle = str(args.get("vehicle") or "").strip() or None

    # 2. Calculate appointment start and end times
    service_info = SERVICES[service]
    service_name = service_info["label"]
    duration = service_info["duration_min"]

    start = combine_date_and_time(date, time)
    end = start + timedelta(minutes=duration)
    now = utils.now_local()

    # 3. Avoid creating a duplicate booking
    existing_events = gcal.find_by_phone(phone, now)

    for event in existing_events:
        same_time = gcal.event_start(event) == start
        same_service = private_properties(event).get("service") == service

        if same_time and same_service:
            return (
                f"ALREADY BOOKED: {service_name} on {fmt_human(start)}. "
                f"event_id={event['id']}"
            )

    # 4. Check the calendar again before booking
    busy_times = busy_intervals_for_day(date)

    available, reason = slots.is_slot_free(
        start,
        duration,
        busy_times,
        HOURS,
        TZ,
        now,
        POLICIES,
        GRANULARITY,
    )

    if not available:
        raise ToolError(
            f"Cannot book: {reason} "
            "Call check_availability to find another time."
        )

    # 5. Prepare the calendar event details
    description = (
        f"Vehicle: {vehicle or 'not given'}\n"
        f"Phone: {phone}\n"
        f"Caller: {name}\n"
        "--- notes ---\n"
    )

    # 6. Create the appointment in Google Calendar
    event = gcal.create_event(
        f"{service_name} - {name}",
        start,
        end,
        description,
        {
            "phone": phone,
            "service": service,
            "created_by": "agent",
            "name": name,
        },
    )

    # 7. Update the current call's state
    session.state.name = name
    session.state.event_id = event["id"]
    session.state.vehicle = vehicle or session.state.vehicle

    set_call_outcome(session, "booked")

    record_in_call_state(
        session,
        "booking",
        f"Booked {service_name} {fmt_human(start)}",
    )

    # 8. Return the booking result
    price = SERVICES[service]["price"]

    return (
        f"BOOKED: {service_name} for {name} on "
        f"{fmt_human(start)} to {fmt_time(end)}. "
        f"Price from ${price} (plus vehicle surcharge if any). "
        f"event_id={event['id']}"
    )


def find_appointments(args, session):
    # Find appointments associated with the caller's phone number
    phone = resolve_caller_phone(session, args)
    now = utils.now_local()

    events = gcal.find_by_phone(phone, now)

    if not events:
        return "No upcoming appointments found under that phone number."

    # Prepare a readable list of appointments
    appointment_lines = []

    for event in events:
        service = private_properties(event).get("service")

        service_name = SERVICES.get(service, {}).get(
            "label",
            event.get("summary"),
        )

        appointment_lines.append(
            f"- {fmt_human(gcal.event_start(event))} | "
            f"{service_name} | event_id={event['id']}"
        )

    return "Upcoming appointments:\n" + "\n".join(appointment_lines)


def notice_window_warning(event):
    # Check whether the appointment is too close to its start time
    notice_hours = POLICIES["cancel_notice_hours"]

    time_remaining = gcal.event_start(event) - utils.now_local()

    if time_remaining < timedelta(hours=notice_hours):
        return (
            f" Note: this was inside our {notice_hours}-hour notice window. "
            f"Mention we ask for {notice_hours} hours notice, "
            "but do NOT mention any fee."
        )

    return ""


def reschedule(args, session):
    # 1. Find and verify the caller's appointment
    phone = resolve_caller_phone(session, args)

    event = load_callers_event(
        phone,
        args.get("event_id"),
    )

    service = private_properties(event).get("service")

    if service not in SERVICES:
        raise ToolError(
            "This appointment has no service on record. "
            "Offer handoff_to_human."
        )

    # 2. Calculate the new appointment time
    new_date = parse_date_arg(args, "new_date")
    new_time = parse_time_arg(args, "new_time")

    new_start = combine_date_and_time(new_date, new_time)

    service_name = SERVICES[service]["label"]
    duration = SERVICES[service]["duration_min"]

    new_end = new_start + timedelta(minutes=duration)
    now = utils.now_local()

    # 3. Check whether the new time is available
    busy_times = busy_intervals_for_day(
        new_date,
        exclude_event_id=event["id"],
    )

    available, reason = slots.is_slot_free(
        new_start,
        duration,
        busy_times,
        HOURS,
        TZ,
        now,
        POLICIES,
        GRANULARITY,
    )

    if not available:
        raise ToolError(
            f"Cannot move it: {reason} "
            "Call check_availability to find another time."
        )

    # 4. Prepare the updated event description
    old_time = fmt_human(gcal.event_start(event))

    warning = notice_window_warning(event)

    description = (
        (event.get("description") or "")
        + f"\nRescheduled from {old_time} at {fmt_human(now)}"
    )

    # 5. Update the appointment in Google Calendar
    gcal.patch_event(
        event["id"],
        {
            "start": {
                "dateTime": new_start.isoformat(),
                "timeZone": TZ.key,
            },
            "end": {
                "dateTime": new_end.isoformat(),
                "timeZone": TZ.key,
            },
            "description": description,
        },
    )

    # 6. Record the change in the current call
    session.state.event_id = event["id"]

    set_call_outcome(session, "rescheduled")

    record_in_call_state(
        session,
        "reschedule",
        f"Rescheduled {service_name} from {old_time} "
        f"to {fmt_human(new_start)}",
    )

    return (
        f"RESCHEDULED: {service_name} moved from {old_time} "
        f"to {fmt_human(new_start)} to {fmt_time(new_end)}."
        f"{warning}"
    )


def cancel(args, session):
    # 1. Find and verify the caller's appointment
    phone = resolve_caller_phone(session, args)

    event = load_callers_event(
        phone,
        args.get("event_id"),
    )

    service = private_properties(event).get("service")

    service_name = SERVICES.get(
        service,
        {},
    ).get("label", "appointment")

    appointment_time = fmt_human(gcal.event_start(event))

    warning = notice_window_warning(event)

    # 2. Delete the appointment from Google Calendar
    gcal.delete_event(event["id"])

    # 3. Record the cancellation
    session.state.event_id = event["id"]

    set_call_outcome(session, "cancelled")

    record_in_call_state(
        session,
        "cancel",
        f"Cancelled {service_name} on {appointment_time}",
    )

    return (
        f"CANCELLED: {service_name} on {appointment_time}."
        f"{warning}"
    )


def note_running_late(args, session):
    # 1. Get the caller's details and validate the delay
    phone = resolve_caller_phone(session, args)

    try:
        minutes_late = int(args.get("minutes"))
    except (TypeError, ValueError):
        raise ToolError("'minutes' must be a whole number.")

    if not 1 <= minutes_late <= 240:
        raise ToolError("'minutes' must be between 1 and 240.")

    now = utils.now_local()

    # 2. Find the appointment if no event ID was supplied
    event_id = args.get("event_id")

    if not event_id:
        todays_events = [
            event
            for event in gcal.find_by_phone(phone, now)
            if gcal.event_start(event).date() == now.date()
        ]

        if not todays_events:
            raise ToolError(
                "No appointment today under that phone number. "
                "Ask which day, or offer handoff_to_human."
            )

        if len(todays_events) > 1:
            raise ToolError(
                "Several appointments today. "
                "Ask which one, then pass event_id."
            )

        event_id = todays_events[0]["id"]

    # 3. Verify the appointment belongs to the caller
    event = load_callers_event(phone, event_id)

    # 4. Add a note to the calendar event
    description = (
        (event.get("description") or "")
        + f"\n[{fmt_human(now)}] "
        f"Caller says running {minutes_late} min late."
    )

    gcal.patch_event(
        event["id"],
        {"description": description},
    )

    # 5. Record the update in the current call
    session.state.event_id = event["id"]

    record_in_call_state(
        session,
        "running_late",
        f"Running {minutes_late} min late",
    )

    # 6. Decide what to tell the caller
    grace_period = POLICIES["late_grace_min"]

    if minutes_late <= grace_period:
        return (
            f"NOTED: running {minutes_late} min late is within "
            f"our {grace_period}-minute grace period. "
            "We'll hold the bay."
        )

    return (
        f"NOTED: {minutes_late} min is over our "
        f"{grace_period}-minute grace period and we may not be "
        "able to hold the bay. OFFER TO RESCHEDULE: use "
        "check_availability then reschedule if they agree."
    )
