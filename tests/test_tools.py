"""Tool-layer tests with an in-memory fake Calendar. No Google network calls."""
from datetime import date, datetime, timedelta

import pytest

import gcal as real_gcal
import tools
import tools.appointments as appointment_tools
import tools.availability as availability_tools
import tools.helpers as helper_tools
import utils
from config import TZ
from session import Session

NOW = datetime(2026, 10, 30, 9, 0, tzinfo=TZ)  # Friday 9 AM, shop local time
THU = date(2026, 11, 5)
ME = "+919876543210"
OTHER = "+919876543211"


def at(day, hour, minute=0):
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=TZ)


class FakeGcal:
    """Implements only the Calendar operations used by the tools under test."""

    event_start = staticmethod(real_gcal.event_start)
    event_end = staticmethod(real_gcal.event_end)

    def __init__(self):
        self.events = {}
        self._next_id = 0

    def add(self, start, end, phone=None, service=None, summary="Busy"):
        self._next_id += 1
        event = {
            "id": f"e{self._next_id}",
            "summary": summary,
            "status": "confirmed",
            "description": "",
            "start": {"dateTime": start.isoformat()},
            "end": {"dateTime": end.isoformat()},
        }
        if phone:
            event["extendedProperties"] = {
                "private": {"phone": phone, "service": service or "exterior_wash"}
            }
        self.events[event["id"]] = event
        return event

    def busy_intervals(self, start, end, exclude_event_id=None):
        return [
            (self.event_start(event), self.event_end(event))
            for event in self.events.values()
            if event["id"] != exclude_event_id
        ]

    def create_event(self, summary, start, end, description, private_props):
        event = self.add(start, end, summary=summary)
        event["description"] = description
        event["extendedProperties"] = {"private": dict(private_props)}
        return event

    def get_event(self, event_id):
        return self.events[event_id]

    def patch_event(self, event_id, body):
        self.events[event_id].update(body)

    def delete_event(self, event_id):
        del self.events[event_id]

    def find_by_phone(self, phone, from_dt):
        return [
            event
            for event in self.events.values()
            if event.get("extendedProperties", {}).get("private", {}).get("phone") == phone
            and self.event_end(event) > from_dt
        ]


@pytest.fixture
def cal(monkeypatch):
    fake = FakeGcal()
    # Patch the modules that actually hold the gcal references used by tools.
    monkeypatch.setattr(appointment_tools, "gcal", fake)
    monkeypatch.setattr(availability_tools, "gcal", fake)
    monkeypatch.setattr(helper_tools, "gcal", fake)
    monkeypatch.setattr(utils, "now_local", lambda: NOW)
    return fake


def sess(phone=ME):
    return Session("test-session", caller_phone=phone)


def run(name, args, session=None):
    return tools.execute(name, args, session or sess())


BOOK = {
    "name": "Sara",
    "service": "exterior_wash",
    "date": "2026-11-05",
    "time": "10:00",
}


def test_booking_taken_slot_refused(cal):
    cal.add(at(THU, 15, 30), at(THU, 16, 30))
    out = run("book_appointment", {**BOOK, "time": "15:30"})
    assert out.startswith("ERROR") and len(cal.events) == 1


def test_booking_success_stores_identity(cal):
    out = run("book_appointment", {**BOOK, "phone": "9999999999", "vehicle": "Civic"})
    assert out.startswith("BOOKED")
    event = next(iter(cal.events.values()))
    assert event["extendedProperties"]["private"]["phone"] == ME  # session phone wins
    assert event["extendedProperties"]["private"]["created_by"] == "agent"


def test_booking_is_idempotent(cal):
    run("book_appointment", BOOK)
    assert run("book_appointment", BOOK).startswith("ALREADY BOOKED")
    assert len(cal.events) == 1


def test_booking_past_closing_refused(cal):
    out = run("book_appointment", {**BOOK, "time": "17:30"})
    assert out.startswith("ERROR") and "closing" in out and not cal.events


def test_booking_on_closed_day_refused(cal):
    assert "closed" in run("book_appointment", {**BOOK, "date": "2026-11-08"})


def test_booking_in_past_refused(cal):
    assert run("book_appointment", {**BOOK, "date": "2026-10-29"}).startswith("ERROR")


def test_bad_inputs(cal):
    assert run("book_appointment", {**BOOK, "service": "polish"}).startswith("ERROR")
    assert run("book_appointment", {**BOOK, "date": "next thursday"}).startswith("ERROR")
    assert run("book_appointment", {**BOOK, "time": "teatime"}).startswith("ERROR")
    assert run("book_appointment", {**BOOK, "name": ""}).startswith("ERROR")
    assert run("book_appointment", {**BOOK, "phone": "123"}, Session("no-phone")).startswith("ERROR")
    assert run("book_appointment", BOOK, Session("no-phone")).startswith("ERROR")
    assert not cal.events


def test_chat_mode_uses_stated_phone(cal):
    out = run("book_appointment", {**BOOK, "phone": "098765 43210"}, Session("chat-session"))
    assert out.startswith("BOOKED")
    event = next(iter(cal.events.values()))
    assert event["extendedProperties"]["private"]["phone"] == ME


def test_reschedule_own_ok_and_can_overlap_old_slot(cal):
    event = cal.add(at(THU, 10), at(THU, 11), phone=ME, service="exterior_wash")
    out = run("reschedule", {"event_id": event["id"], "new_date": "2026-11-05", "new_time": "10:30"})
    assert out.startswith("RESCHEDULED")
    assert cal.event_start(cal.events[event["id"]]) == at(THU, 10, 30)
    assert cal.event_end(cal.events[event["id"]]) == at(THU, 11, 30)


def test_reschedule_into_conflict_refused(cal):
    event = cal.add(at(THU, 10), at(THU, 11), phone=ME, service="exterior_wash")
    cal.add(at(THU, 14), at(THU, 15))
    out = run("reschedule", {"event_id": event["id"], "new_date": "2026-11-05", "new_time": "14:00"})
    assert out.startswith("ERROR")
    assert cal.event_start(cal.events[event["id"]]) == at(THU, 10)


def test_reschedule_other_phone_refused(cal):
    event = cal.add(at(THU, 10), at(THU, 11), phone=OTHER, service="exterior_wash")
    out = run("reschedule", {"event_id": event["id"], "new_date": "2026-11-05", "new_time": "12:00"})
    assert out.startswith("ERROR")
    assert cal.event_start(cal.events[event["id"]]) == at(THU, 10)


def test_seeded_event_without_phone_refused(cal):
    event = cal.add(at(THU, 10), at(THU, 11))
    assert run("reschedule", {"event_id": event["id"], "new_date": "2026-11-05", "new_time": "12:00"}).startswith("ERROR")
    assert run("cancel", {"event_id": event["id"]}).startswith("ERROR")
    assert event["id"] in cal.events


def test_cancel_own_and_unknown_id(cal):
    event = cal.add(at(THU, 10), at(THU, 11), phone=ME)
    assert run("cancel", {"event_id": event["id"]}).startswith("CANCELLED")
    assert event["id"] not in cal.events
    assert run("cancel", {"event_id": "nope"}).startswith("ERROR")


def test_running_late_grace_vs_over(cal):
    today = date(2026, 10, 30)
    event = cal.add(at(today, 14), at(today, 15), phone=ME, service="exterior_wash")
    within_grace = run("note_running_late", {"minutes": 10})
    over_grace = run("note_running_late", {"minutes": 30, "event_id": event["id"]})
    assert within_grace.startswith("NOTED") and "OFFER TO RESCHEDULE" not in within_grace
    assert "OFFER TO RESCHEDULE" in over_grace
    assert "running 30 min late" in cal.events[event["id"]]["description"]


def test_running_late_no_appointment_today(cal):
    assert run("note_running_late", {"minutes": 10}).startswith("ERROR")


def test_availability_taken_slot_offers_alternatives(cal):
    cal.add(at(THU, 15, 30), at(THU, 16, 30))
    out = run("check_availability", {"service": "exterior_wash", "date": "2026-11-05", "time": "15:30"})
    # The configured shop closes at 5 PM, so 4:30 PM would run past closing.
    assert out.startswith("NOT AVAILABLE") and "2:30 PM" in out


def test_availability_open_and_closed(cal):
    assert run("check_availability", {"service": "exterior_wash", "date": "2026-11-05", "time": "10:00"}).startswith("AVAILABLE")
    out = run("check_availability", {"service": "exterior_wash", "date": "2026-11-08"})
    assert "closed" in out and "Next availability" in out


def test_availability_full_day_points_to_next_day(cal):
    cal.add(at(THU, 0), at(THU, 0) + timedelta(days=1))
    out = run("check_availability", {"service": "exterior_wash", "date": "2026-11-05"})
    assert "Next availability" in out and "Fri Nov 6" in out


def test_vehicles(cal):
    assert "NOT SUPPORTED" in run("check_vehicle", {"vehicle_type": "motorcycle"})
    out = run("check_vehicle", {"vehicle_type": "SUVs"})
    assert "SUPPORTED" in out and "$20" in out
    assert run("check_vehicle", {"vehicle_type": "pickup"}).count("$30") == 1
    assert run("check_vehicle", {"vehicle_type": "1950 Airstream"}).startswith("UNKNOWN")


def test_info_and_handoff(cal):
    assert "$150" in run("get_info", {"topic": "pricing"})
    assert run("get_info", {"topic": "gossip"}).startswith("ERROR")
    session = sess()
    out = run("handoff_to_human", {"reason": "wants refund", "category": "complaint"}, session)
    assert out.startswith("HANDOFF")
    assert session.state.outcome == "handed_off" and session.state.needs_followup


def test_handoff_outcome_not_overwritten(cal):
    session = sess()
    run("handoff_to_human", {"reason": "angry"}, session)
    run("book_appointment", BOOK, session)
    assert session.state.outcome == "handed_off"


def test_execute_robustness(cal):
    assert run("nope", {}).startswith("ERROR")
    assert tools.execute("get_info", '{"topic": "hours"}', sess()).startswith("Hours")
    assert tools.execute("get_info", "{not json", sess()).startswith("ERROR")
    assert tools.execute("get_info", None, sess()).startswith("ERROR")
