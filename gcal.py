"""Thin Google Calendar wrapper. No business rules here, except: EVERY event is busy
(including hand-made ones), unless cancelled or marked 'free' (transparent)."""

from datetime import date,datetime,time
import config

_service=None

def _svc():
    global _service
    if _service is None:
        from googleapiclient.discovery import build
        from google_auth import get_credentials
        _service = build("calendar", "v3", credentials=get_credentials(), cache_discovery=False)
    return _service


# converts iso datetime string to python datetime object
def _parse_dt(s):
    return datetime.fromisoformat(s.replace("Z","+00:00"))

# extracts the start time of a Google Calendar event
def event_start(ev):
    s = ev["start"]
    if "dateTime" in s:
        return _parse_dt(s["dateTime"]).astimezone(config.TZ)
    return datetime.combine(
        date.fromisoformat(s["date"]),
        time.min,
        tzinfo=config.TZ
    )
    
# extracts the end time of a Google Calendar event
def event_end(ev):
    e = ev["end"]
    if "dateTime" in e:
        return _parse_dt(e["dateTime"]).astimezone(config.TZ)
    return datetime.combine(
        date.fromisoformat(e["date"]),
        time.min,
        tzinfo=config.TZ
    )  # exclusive end
    
# retrieves events from Google Calendar
def _list(**kw):
    items, token = [], None
    while True:
        resp = _svc().events().list(
            calendarId=config.CALENDAR_ID,
            singleEvents=True,
            orderBy="startTime",
            maxResults=250,
            pageToken=token,
            **kw
        ).execute()
        items += resp.get("items", [])
        token = resp.get("nextPageToken")
        if not token:
            return items
        
# retrieves calendar events between a start and end datetime
def list_events(start, end):
    return _list(timeMin=start.isoformat(), timeMax=end.isoformat())

# return the time intervals that should be considered occupied
def busy_intervals(start, end, exclude_event_id=None):
    out = []
    for ev in list_events(start, end):
        if ev.get("status") == "cancelled" or ev.get("transparency") == "transparent":
            continue
        if exclude_event_id and ev["id"] == exclude_event_id:
            continue
        out.append((event_start(ev), event_end(ev)))
    return out

# create event
def create_event(summary, start, end, description, private_props):
    body = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start.isoformat(), "timeZone": config.TZ.key},
        "end": {"dateTime": end.isoformat(), "timeZone": config.TZ.key},
        "extendedProperties": {"private": {k: str(v) for k, v in private_props.items()}},
    }
    return insert_raw(body)

# insert event
def insert_raw(body):
    return _svc().events().insert(calendarId=config.CALENDAR_ID, body=body).execute()

# get event
def get_event(event_id):
    return _svc().events().get(calendarId=config.CALENDAR_ID, eventId=event_id).execute()

# patch event
def patch_event(event_id, body):
    return _svc().events().patch(calendarId=config.CALENDAR_ID, eventId=event_id, body=body).execute()


#delete event
def delete_event(event_id):
    _svc().events().delete(calendarId=config.CALENDAR_ID, eventId=event_id).execute()

# list events by extra private properties
def list_by_private_prop(key, value, from_dt=None):
    kw = {"privateExtraProperty": f"{key}={value}"}
    if from_dt is not None:
        kw["timeMin"] = from_dt.isoformat()
    return [e for e in _list(**kw) if e.get("status") != "cancelled"]

# find events by phone number
def find_by_phone(phone, from_dt):
    """Upcoming events whose private.phone matches (server-side filter)."""
    return list_by_private_prop("phone", phone, from_dt)
