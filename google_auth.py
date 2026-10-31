import os
from pathlib import Path

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/spreadsheets",
]
ROOT = Path(__file__).resolve().parent
KEY_FILE = Path(os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or ROOT / "credentials/service-account.json")

def get_credentials():
    from google.oauth2 import service_account
    return service_account.Credentials.from_service_account_file(str(KEY_FILE), scopes=SCOPES)