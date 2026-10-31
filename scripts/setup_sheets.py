"""Creates the Contacts and Call Log tabs (if missing) and writes header rows. Safe to rerun."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
import sheets  # noqa: E402


def main():
    if not config.SHEET_ID:
        raise SystemExit("Set SHEET_ID in .env first (the long id in the sheet URL).")
    svc = sheets.get_service()
    meta = svc.spreadsheets().get(spreadsheetId=config.SHEET_ID).execute()
    existing = {s["properties"]["title"] for s in meta["sheets"]}
    reqs = [{"addSheet": {"properties": {"title": t}}} for t in sheets.HEADERS if t not in existing]
    if reqs:
        svc.spreadsheets().batchUpdate(spreadsheetId=config.SHEET_ID, body={"requests": reqs}).execute()
    for title, headers in sheets.HEADERS.items():
        svc.spreadsheets().values().update(
            spreadsheetId=config.SHEET_ID, range=f"'{title}'!A1", valueInputOption="RAW",
            body={"values": [headers]}).execute()
    print("Sheet ready:", ", ".join(sheets.HEADERS))


if __name__ == "__main__":
    main()
