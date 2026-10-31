"""Tools that answer from shop.yaml (get_info, check_vehicle) and the human handoff."""
import re

import slots
from config import HOURS, POLICIES, PREP, SERVICES, SHOP, VEHICLES
from utils import fmt_hhmm

from .helpers import CATEGORY_PRIORITY, ToolError, record_in_call_state

# Which call category each get_info topic counts as, for logging.
TOPIC_TO_CATEGORY = {"pricing": "pricing", "hours": "hours", "prep": "prep", "vehicles": "vehicle_check",
                     "policies": "other"}


# Tool: returns official pricing, hours, prep rules, vehicle rules or policies, all read from shop.yaml.
# The model must use this instead of stating such facts from memory.
def get_info(args, session):
    topic = str(args.get("topic", "")).strip().lower()

    if topic == "pricing":
        price_lines = [f"{service['label']} ${service['price']} ({service['duration_min']} min)"
                       for service in SERVICES.values()]
        surcharges = VEHICLES.get("surcharge") or {}
        info_text = "Starting prices: " + "; ".join(price_lines) + "."
        if surcharges:
            surcharge_lines = [f"{vehicle.upper() if vehicle == 'suv' else vehicle} +${amount}"
                               for vehicle, amount in surcharges.items()]
            info_text += " Vehicle surcharges: " + ", ".join(surcharge_lines) + "."

    elif topic == "hours":
        hours_lines = []
        for day_key in slots.DAY_KEYS:
            if day_key in HOURS:
                opens, closes = HOURS[day_key]
                hours_lines.append(f"{day_key.title()}: {fmt_hhmm(opens)} to {fmt_hhmm(closes)}")
            else:
                hours_lines.append(f"{day_key.title()}: closed")
        info_text = "Hours: " + "; ".join(hours_lines) + "."

    elif topic == "prep":
        info_text = "Prep requirements: " + " ".join(PREP)

    elif topic == "vehicles":
        surcharges = VEHICLES.get("surcharge") or {}
        surcharge_text = ", ".join(f"{vehicle} +${amount}" for vehicle, amount in surcharges.items()) or "none"
        info_text = ("We detail: " + ", ".join(VEHICLES["supported"]) + ". We do NOT detail: "
                     + ", ".join(VEHICLES["unsupported"]) + ". Surcharges: " + surcharge_text + ".")

    elif topic == "policies":
        info_text = (f"Late grace period: {POLICIES['late_grace_min']} minutes (we hold the bay that long). "
                     f"We ask for {POLICIES['cancel_notice_hours']} hours notice to cancel or reschedule. "
                     f"Bookings need {POLICIES['min_booking_notice_hours']} hours notice and can be made up to "
                     f"{POLICIES['max_days_ahead']} days ahead. For fees or anything not listed, hand off.")

    else:
        raise ToolError("topic must be one of: pricing, hours, prep, vehicles, policies.")

    record_in_call_state(session, TOPIC_TO_CATEGORY[topic], f"Asked about {topic}")
    return info_text


# Informal vehicle words mapped to the body types used in shop.yaml.
_VEHICLE_ALIASES = {"pickup": "truck", "pick-up": "truck", "crossover": "suv", "van": "minivan",
                    "motorbike": "motorcycle", "scooter": "motorcycle", "motorhome": "rv", "camper": "rv"}


# True if `word` appears as a whole word in `text`, allowing a plural "s" (so "SUVs" matches "suv").
def _contains_word(text, word):
    return re.search(rf"\b{re.escape(word)}s?\b", text) is not None


# Tool: says whether we detail a given vehicle type: SUPPORTED (with any surcharge), NOT SUPPORTED, or UNKNOWN.
# UNKNOWN tells the model to ask once for the body style, then hand off if still unsure.
def check_vehicle(args, session):
    caller_description = str(args.get("vehicle_type", "")).strip().lower()
    if not caller_description:
        raise ToolError("vehicle_type is required.")

    normalized_text = caller_description
    for informal_word, body_type in _VEHICLE_ALIASES.items():
        normalized_text = re.sub(rf"\b{re.escape(informal_word)}s?\b", body_type, normalized_text)

    for body_type in VEHICLES["unsupported"]:
        if _contains_word(normalized_text, body_type):
            record_in_call_state(session, "vehicle_check", f"Asked about {caller_description}: not supported")
            return f"NOT SUPPORTED: we don't detail {body_type}s. Tell the caller politely."

    for body_type in VEHICLES["supported"]:
        if _contains_word(normalized_text, body_type):
            surcharge = (VEHICLES.get("surcharge") or {}).get(body_type)
            record_in_call_state(session, "vehicle_check", f"Asked about {caller_description}: supported")
            surcharge_text = f" Surcharge: +${surcharge}." if surcharge else " No surcharge."
            return f"SUPPORTED: yes, we detail {body_type}s.{surcharge_text}"

    record_in_call_state(session, "vehicle_check", f"Asked about {caller_description}: unknown")
    return ("UNKNOWN vehicle type. Ask once what body style it is (sedan, SUV, truck...). "
            "If they can't say or it's unusual, call handoff_to_human.")


# Tool: hands the caller to a human. Records the reason and flags the call for follow-up.
# Returns instructions telling the model what to say, so it doesn't try to solve the issue itself.
def handoff_to_human(args, session):
    reason = str(args.get("reason", "")).strip() or "unspecified"
    category = str(args.get("category", "other")).strip().lower()
    if category not in CATEGORY_PRIORITY:
        category = "other"

    call_state = session.state
    call_state.outcome = "handed_off"
    call_state.handoff_reason = reason
    call_state.needs_followup = True
    record_in_call_state(session, category, f"Handed off: {reason}")
    return (f"HANDOFF RECORDED. Tell the caller a team member will follow up shortly, confirm the best "
            f"callback number if you don't have it, and mention the shop number {SHOP['phone']}. "
            f"Do not try to resolve the issue yourself.")