from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

import slots

TZ = ZoneInfo("Asia/Kolkata")
HOURS = {d: ["08:00", "18:00"] for d in ["mon", "tue", "wed", "thu", "fri"]}
HOURS["sat"] = ["09:00", "15:00"]
POL = {"min_booking_notice_hours": 2, "max_days_ahead": 60}
NOW = datetime(2026, 10, 30, 9, 0, tzinfo=TZ)   # Friday
THU = date(2026, 11, 5)
SAT = date(2026, 11, 7)
SUN = date(2026, 11, 8)


def at(d, h, m=0):
    return datetime(d.year, d.month, d.day, h, m, tzinfo=TZ)


def hm(starts):
    return {(s.hour, s.minute) for s in starts}


def free(d, dur, busy=(), now=NOW):
    return slots.free_starts(d, dur, list(busy), HOURS, TZ, now, POL, 30)


def ok(start, dur, busy=(), now=NOW):
    return slots.is_slot_free(start, dur, list(busy), HOURS, TZ, now, POL, 30)


def test_empty_day():
    r = free(THU, 60)
    assert len(r) == 19
    assert (r[0].hour, r[0].minute) == (8, 0)
    assert (r[-1].hour, r[-1].minute) == (17, 0)


def test_busy_block_in_middle():
    r = hm(free(THU, 60, [(at(THU, 10), at(THU, 12))]))
    assert (9, 0) in r             # ends exactly at 10:00
    assert (9, 30) not in r
    assert (11, 30) not in r
    assert (12, 0) in r             # starts exactly when busy ends


def test_back_to_back_allowed():
    assert ok(at(THU, 12), 60, [(at(THU, 10), at(THU, 12))])[0]


def test_runs_past_closing():
    good, reason = ok(at(THU, 17, 30), 60)
    assert not good and "closing" in reason


def test_closed_day():
    good, reason = ok(at(SUN, 10), 60)
    assert not good and "closed" in reason
    assert free(SUN, 60) == []


def test_saturday_closing():
    assert ok(at(SAT, 12), 180)[0]
    assert not ok(at(SAT, 12, 30), 180)[0]


def test_before_opening():
    good, reason = ok(at(THU, 7), 60)
    assert not good and "open" in reason


def test_past_and_min_notice():
    now = at(THU, 9)
    assert "passed" in ok(at(THU, 8), 60, now=now)[1]
    assert "notice" in ok(at(THU, 10), 60, now=now)[1]
    assert ok(at(THU, 11), 60, now=now)[0]


def test_max_days_ahead():
    start = (NOW + timedelta(days=61)).replace(hour=10, minute=0)
    good, reason = ok(start, 60)
    assert not good and "days ahead" in reason


def test_bad_granularity():
    assert not ok(at(THU, 8, 15), 60)[0]


def test_ceramic_fits_nowhere_on_busy_day():
    assert hm(free(THU, 480)) == {(8, 0), (8, 30), (9, 0), (9, 30), (10, 0)}
    assert free(THU, 480, [(at(THU, 12), at(THU, 13))]) == []


def test_event_straddling_opening():
    busy = [(at(THU, 7), at(THU, 9))]
    assert not ok(at(THU, 8), 60, busy)[0]
    assert ok(at(THU, 9), 60, busy)[0]


def test_all_day_event():
    busy = [(at(THU, 0), at(THU, 0) + timedelta(days=1))]
    assert free(THU, 60, busy) == []


def test_naive_datetime_rejected():
    with pytest.raises(ValueError):
        slots.is_slot_free(datetime(2026, 11, 5, 10), 60, [], HOURS, TZ, NOW, POL)


def test_free_starts_agrees_with_is_slot_free():
    busy = [(at(THU, 10), at(THU, 12)), (at(THU, 15, 30), at(THU, 16, 30))]
    allowed = hm(free(THU, 90, busy))
    for h in range(7, 19):
        for m in (0, 30):
            assert ok(at(THU, h, m), 90, busy)[0] == ((h, m) in allowed)