"""Google Sheets wrapper for contacts and call logs."""

import config
import utils

CONTACT_HEADERS = [
    "phone", "name", "vehicle", "first_seen", "last_call",
    "call_count", "last_category", "last_summary", "needs_followup"
]

LOG_HEADERS = [
    "timestamp", "session_id", "phone", "name", "category",
    "summary", "outcome", "event_id", "handoff_reason"
]

HEADERS = {
    "Contacts": CONTACT_HEADERS,
    "Call Log": LOG_HEADERS,
}

_service = None


def normalize_indian_phone(phone):
    """Normalize contacts with the same E.164 rules used by the receptionist."""
    normalized = utils.normalize_phone(phone)
    if not normalized:
        raise ValueError("Enter a valid phone number in international format or an Indian mobile format.")
    return normalized


def get_service():
    """Create the Google Sheets connection once and reuse it."""
    global _service

    if _service is None:
        from googleapiclient.discovery import build
        from google_auth import get_credentials

        _service = build(
            "sheets",
            "v4",
            credentials=get_credentials(),
            cache_discovery=False,
        )

    return _service


def get_values():
    return get_service().spreadsheets().values()


def pad_row(row, length):
    """Fill missing spreadsheet cells with empty strings."""
    return list(row) + [""] * (length - len(row))


def upsert_contact(
    phone,
    name=None,
    vehicle=None,
    category=None,
    summary=None,
    needs_followup=None,
    now=None,
):
    """Create a contact or update the existing contact for this phone."""

    phone = normalize_indian_phone(phone)
    now_text = (now or utils.now_local()).isoformat(timespec="seconds")

    # Read existing contacts
    values = get_values()
    rows = values.get(
        spreadsheetId=config.SHEET_ID,
        range="Contacts!A2:I",
    ).execute().get("values", [])

    # Find the contact, even if an older row uses another Indian format
    index = None

    for i, row in enumerate(rows):
        if row and row[0]:
            try:
                if normalize_indian_phone(row[0]) == phone:
                    index = i
                    break
            except ValueError:
                # Ignore old rows with invalid phone numbers
                continue

    if index is None:
        # Create a new contact
        row = [
            phone,
            name or "",
            vehicle or "",
            now_text,
            now_text,
            1,
            category or "",
            summary or "",
            "TRUE" if needs_followup else "FALSE",
        ]

        values.append(
            spreadsheetId=config.SHEET_ID,
            range="Contacts!A:I",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()

        return "created"

    # Update the existing contact
    row = pad_row(rows[index], 9)

    row[0] = phone
    row[1] = name or row[1]
    row[2] = vehicle or row[2]
    row[4] = now_text

    try:
        row[5] = int(row[5] or 0) + 1
    except (ValueError, TypeError):
        row[5] = 1

    row[6] = category or row[6]
    row[7] = summary or row[7]

    # Never accidentally clear an existing follow-up flag
    if needs_followup:
        row[8] = "TRUE"

    sheet_row = index + 2

    values.update(
        spreadsheetId=config.SHEET_ID,
        range=f"Contacts!A{sheet_row}:I{sheet_row}",
        valueInputOption="RAW",
        body={"values": [row]},
    ).execute()

    return "updated"


def append_call_log(
    timestamp,
    session_id,
    phone,
    name,
    category,
    summary,
    outcome,
    event_id="",
    handoff_reason="",
):
    """Append one call record to the Call Log sheet."""

    if phone:
        phone = normalize_indian_phone(phone)

    row = [
        timestamp,
        session_id,
        phone or "",
        name or "",
        category or "",
        summary or "",
        outcome or "",
        event_id or "",
        handoff_reason or "",
    ]

    get_values().append(
        spreadsheetId=config.SHEET_ID,
        range="'Call Log'!A:I",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()
