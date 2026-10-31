"""Finds the requested tool and executes it safely."""

import json
import logging

from .appointments import (
    book_appointment,
    cancel,
    find_appointments,
    note_running_late,
    reschedule
)

from .availability import check_availability
from .helpers import ToolError
from .information import check_vehicle, get_info, handoff_to_human


# Set up logging
log = logging.getLogger(__name__)


# Store all available tools in a dictionary
TOOLS = {
    "check_availability": check_availability,
    "book_appointment": book_appointment,
    "find_appointments": find_appointments,
    "reschedule": reschedule,
    "cancel": cancel,
    "note_running_late": note_running_late,
    "get_info": get_info,
    "check_vehicle": check_vehicle,
    "handoff_to_human": handoff_to_human
}


def execute(name, args, session):
    """Execute a tool and return the result as a string."""

    # Step 1: Find the requested tool
    function = TOOLS.get(name)

    if function is None:
        return f"ERROR: unknown tool '{name}'."

    # Step 2: Convert JSON text into a Python dictionary
    if isinstance(args, str):
        try:
            args = json.loads(args or "{}")
        except json.JSONDecodeError:
            return "ERROR: tool arguments were not valid JSON."

    # Step 3: Check that arguments are a dictionary
    if not isinstance(args, dict):
        return "ERROR: tool arguments must be an object."

    # Step 4: Execute the function
    try:
        result = function(args, session)
        return result

    # Step 5: Handle expected errors
    except ToolError as error:
        return f"ERROR: {error}"

    # Step 6: Handle unexpected errors
    except Exception:
        log.exception("tool %s crashed", name)

        return (
            "ERROR: internal problem. "
            "Apologize briefly and call handoff_to_human."
        )
