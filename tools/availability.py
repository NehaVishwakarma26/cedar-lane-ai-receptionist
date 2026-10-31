import re

import slots
from config import HOURS, POLICIES, PREP, SERVICES, SHOP, VEHICLES
from utils import fmt_hhmm

from .helpers import CATEGORY_PRIORITY, ToolError, note


# Which call category should be recorded for each topic?
TOPIC_CATEGORY = {
    "pricing": "pricing",
    "hours": "hours",
    "prep": "prep",
    "vehicles": "vehicle_check",
    "policies": "other",
}


# Answer questions about the shop
def get_info(args, session):
    topic = str(args.get("topic", "")).strip().lower()

    if topic == "pricing":
        services = []

        for service in SERVICES.values():
            services.append(
                f"{service['label']} ${service['price']} "
                f"({service['duration_min']} min)"
            )

        text = "Starting prices: " + "; ".join(services) + "."

        surcharges = VEHICLES.get("surcharge") or {}

        if surcharges:
            extra = []

            for vehicle, price in surcharges.items():
                extra.append(f"{vehicle.upper() if vehicle == 'suv' else vehicle} +${price}")

            text += " Vehicle surcharges: " + ", ".join(extra) + "."

    elif topic == "hours":
        hours = []

        for day in slots.DAY_KEYS:
            if day in HOURS:
                opening = fmt_hhmm(HOURS[day][0])
                closing = fmt_hhmm(HOURS[day][1])
                hours.append(f"{day.title()}: {opening} to {closing}")
            else:
                hours.append(f"{day.title()}: closed")

        text = "Hours: " + "; ".join(hours) + "."

    elif topic == "prep":
        text = "Prep requirements: " + " ".join(PREP)

    elif topic == "vehicles":
        supported = ", ".join(VEHICLES["supported"])
        unsupported = ", ".join(VEHICLES["unsupported"])

        surcharges = VEHICLES.get("surcharge") or {}

        if surcharges:
            extra = ", ".join(
                f"{vehicle} +${price}"
                for vehicle, price in surcharges.items()
            )
        else:
            extra = "none"

        text = (
            f"We detail: {supported}. "
            f"We do NOT detail: {unsupported}. "
            f"Surcharges: {extra}."
        )

    elif topic == "policies":
        text = (
            f"Late grace period: {POLICIES['late_grace_min']} minutes. "
            f"We ask for {POLICIES['cancel_notice_hours']} hours notice "
            f"to cancel or reschedule. "
            f"Bookings need {POLICIES['min_booking_notice_hours']} hours notice "
            f"and can be made up to {POLICIES['max_days_ahead']} days ahead. "
            f"For fees or anything not listed, hand off."
        )

    else:
        raise ToolError(
            "topic must be one of: pricing, hours, prep, vehicles, policies."
        )

    note(session, TOPIC_CATEGORY[topic], f"Asked about {topic}")

    return text


# Alternative names for vehicle types
ALIASES = {
    "pickup": "truck",
    "pick-up": "truck",
    "crossover": "suv",
    "van": "minivan",
    "motorbike": "motorcycle",
    "scooter": "motorcycle",
    "motorhome": "rv",
    "camper": "rv",
}


# Check whether a vehicle name appears in the text
def has_word(text, word):
    pattern = rf"\b{re.escape(word)}s?\b"
    return re.search(pattern, text) is not None


# Check whether the shop accepts a vehicle
def check_vehicle(args, session):
    vehicle = str(args.get("vehicle_type", "")).strip().lower()

    if not vehicle:
        raise ToolError("vehicle_type is required.")

    # Convert alternative names into standard names
    for alias, standard_name in ALIASES.items():
        vehicle = re.sub(
            rf"\b{re.escape(alias)}s?\b",
            standard_name,
            vehicle,
        )

    # Check unsupported vehicles first
    for item in VEHICLES["unsupported"]:
        if has_word(vehicle, item):
            note(
                session,
                "vehicle_check",
                f"Asked about {vehicle}: not supported",
            )
            return f"NOT SUPPORTED: we don't detail {item}s. Tell the caller politely."

    # Check supported vehicles
    for item in VEHICLES["supported"]:
        if has_word(vehicle, item):
            surcharge = VEHICLES.get("surcharge", {}).get(item)

            note(
                session,
                "vehicle_check",
                f"Asked about {vehicle}: supported",
            )

            if surcharge:
                return f"SUPPORTED: yes, we detail {item}s. Surcharge: +${surcharge}."

            return f"SUPPORTED: yes, we detail {item}s. No surcharge."

    # The vehicle could not be identified
    note(
        session,
        "vehicle_check",
        f"Asked about {vehicle}: unknown",
    )

    return (
        "UNKNOWN vehicle type. Ask once what body style it is "
        "(sedan, SUV, truck...). If they can't say or it's unusual, "
        "call handoff_to_human."
    )


# Transfer an issue to a human team member
def handoff_to_human(args, session):
    reason = str(args.get("reason", "")).strip() or "unspecified"

    category = str(args.get("category", "other")).strip().lower()

    if category not in CATEGORY_PRIORITY:
        category = "other"

    state = session.state

    state.outcome = "handed_off"
    state.handoff_reason = reason
    state.needs_followup = True

    note(session, category, f"Handed off: {reason}")

    return (
        "HANDOFF RECORDED. Tell the caller a team member will follow up shortly, "
        "confirm the best callback number if you don't have it, "
        f"and mention the shop number {SHOP['phone']}. "
        "Do not try to resolve the issue yourself."
    )
