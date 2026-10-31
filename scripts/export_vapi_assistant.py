"""Export the assistant JSON to configure in the Vapi dashboard."""

import json
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from tools.schemas import TOOLS  # noqa: E402


def build_assistant_config():
    service_list = ", ".join(service["label"] for service in config.SERVICES.values())
    vapi_tools = []
    for schema in TOOLS:
        tool = dict(schema)
        tool["messages"] = [{"type": "request-start", "content": "One moment while I check that for you."}]
        vapi_tools.append(tool)
    prompt = f"""You are the phone receptionist for {config.SHOP['name']}, an auto detailing shop.
Speak naturally and briefly, one question at a time. Never use markdown or read technical IDs aloud.

Current local date/time: {{{{ "now" | date: "%A, %B %d, %Y %I:%M %p", "{config.TZ.key}" }}}}.
The shop timezone is {config.TZ.key}. Convert relative dates into the correct local calendar date.
Services: {service_list}.
The inbound caller ID is {{{{customer.number}}}}. Use it as the caller's phone number when present; otherwise ask for a reachable number.

Use tools for every price, business hour, policy, prep requirement, vehicle eligibility, and availability answer.
For booking, collect the service, date, time, customer name, and phone if caller ID is unavailable. Check availability first.
Read the exact appointment details back and wait for a clear yes before calling book_appointment.
Do not claim a booking, cancellation, or reschedule succeeded unless the corresponding tool result confirms it.
For rescheduling or cancellation, look up the caller's appointment first and confirm the requested change before acting.
For lateness, identify the appointment before recording it.
If a caller disputes a charge, asks for a refund or a human, reports damage, or needs unsupported help, use handoff_to_human.
Be honest that a handoff is recorded for staff review and is not automatically sent to an employee.
After resolving the request, ask whether the caller needs anything else."""

    server = {"url": config.VAPI_SERVER_URL or "https://YOUR_PUBLIC_HOST/vapi/webhook"}
    if config.VAPI_CREDENTIAL_ID:
        server["credentialId"] = config.VAPI_CREDENTIAL_ID

    return {
        "name": f"{config.SHOP['name']} Voice Receptionist",
        "firstMessage": f"Thanks for calling {config.SHOP['name']}. How can I help you today?",
        "model": {
            "provider": "google",
            "model": config.GEMINI_MODEL,
            "messages": [{"role": "system", "content": prompt}],
            "tools": vapi_tools,
            "maxTokens": 220,
        },
        "transcriber": {"provider": "deepgram", "model": "nova-3", "language": "en"},
        "voice": {"provider": "vapi", "voiceId": "Elliot", "version": 2, "language": "en"},
        "server": server,
        "serverMessages": ["tool-calls", "end-of-call-report"],
        "startSpeakingPlan": {
            "waitSeconds": 0.4,
            "smartEndpointingPlan": {
                "provider": "livekit",
                "waitFunction": "2000 / (1 + exp(-10 * (x - 0.5)))",
            },
        },
        "stopSpeakingPlan": {"numWords": 0, "voiceSeconds": 0.2, "backoffSeconds": 0.8},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write the assistant config to this JSON file.")
    args = parser.parse_args()
    rendered = json.dumps(build_assistant_config(), indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(f"Wrote Vapi assistant config to {args.output}")
    else:
        print(rendered)
