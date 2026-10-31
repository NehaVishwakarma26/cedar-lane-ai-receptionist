"""Seeds test events relative to today. Idempotent: deletes previous seeded events first.

Events WITHOUT a private phone are 'hand-made' => busy, but never changeable by the agent.
"""
import sys
from datetime import datetime, time, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config 
import gcal  
import utils 

TZ = config.TZ
SEED = {"seeded": "true"}

def next_weekday(wd, min_ahead=2, extra_weeks=0):
    d = utils.now_local().date() + timedelta(days=min_ahead)
    while d.weekday() != wd:
        d += timedelta(days=1)
    return d + timedelta(weeks=extra_weeks)


def dt(d, h, m=0):
    return datetime.combine(d, time(h, m), tzinfo=TZ)


def timed(summary, start, end, phone=None, service=None, name=None):
    priv = dict(SEED)
    if phone:
        priv.update({"phone": phone, "service": service, "created_by": "agent", "name": name or ""})
    return {
        "summary": summary,
        "description": f"Phone: {phone}\n--- notes ---\n" if phone else "",
        "start": {"dateTime": start.isoformat(), "timeZone": TZ.key},
        "end": {"dateTime": end.isoformat(), "timeZone": TZ.key},
        "extendedProperties": {"private": priv},
    }


def main():
    for ev in gcal.list_by_private_prop("seeded", "true"):
        gcal.delete_event(ev["id"])

    thu = next_weekday(3)
    tue = next_weekday(1)
    fri = next_weekday(4)
    mon = next_weekday(0)
    sat = next_weekday(5)
    wed_later = next_weekday(2, extra_weeks=1)

    events = [
        # the assignment example: Thursday 3:30 is taken (hand-made, unchangeable)
        timed("Exterior Wash - Mike (walk-in)", dt(thu, 15, 30), dt(thu, 16, 30)),
        # back-to-back pair
        timed("Interior Detail - Lee (hand-made)", dt(tue, 10), dt(tue, 12)),
        timed("Interior Detail - Ortiz (hand-made)", dt(tue, 12), dt(tue, 14)),
        # Saturday near closing (shop closes 3 PM)
        timed("Exterior Wash - Chen (hand-made)", dt(sat, 13), dt(sat, 14)),
        # agent-style events with phones, for reschedule / cancel / identity tests
        timed("Interior Detail - Sara", dt(fri, 9), dt(fri, 11),
              phone="+919876543210", service="interior_detail", name="Sara"),
        timed("Exterior Wash - Dave", dt(mon, 13), dt(mon, 14),
              phone="+919876500111", service="exterior_wash", name="Dave"),
    ]
    # all-day event (date, not dateTime)
    events.append({
        "summary": "Shop closed - staff training",
        "start": {"date": wed_later.isoformat()},
        "end": {"date": (wed_later + timedelta(days=1)).isoformat()},
        "extendedProperties": {"private": dict(SEED)},
    })

    for body in events:
        gcal.insert_raw(body)

    print("Seeded:")
    print(f"  Thu {thu}  15:30-16:30  hand-made (taken slot)")
    print(f"  Tue {tue}  10:00-14:00  two back-to-back hand-made events")
    print(f"  Sat {sat}  13:00-14:00  hand-made, near closing")
    print(f"  Fri {fri}  09:00-11:00  Sara +919876543210 (agent-style, changeable by Sara)")
    print(f"  Mon {mon}  13:00-14:00  Dave +919876500111 (someone else's)")
    print(f"  Wed {wed_later}  all-day: shop closed")


if __name__ == "__main__":
    main()