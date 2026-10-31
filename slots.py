from datetime import datetime,time,timedelta

DAY_KEYS=["mon","tue","wed","thu","fri","sat","sun"]

# string->time
def parse_hhmm(s:str)->time:
    if not isinstance(s,str):
        raise ValueError(f"time must be a quoted 'HH:MM' string, got {s!r}")
    h,m=s.split(":")
    return time(int(h),int(m))

# check for overlap
def overlaps(a_start,a_end,b_start,b_end):
    return a_start<b_end and b_start<a_end

# when does the shop open and close
def open_close(d, hours_cfg, tz):
    """(open_dt, close_dt) for date d, or None if closed."""
    rng = hours_cfg.get(DAY_KEYS[d.weekday()])

    if not rng:
        return None

    o, c = rng

    return (
        datetime.combine(d, parse_hhmm(o), tzinfo=tz),
        datetime.combine(d, parse_hhmm(c), tzinfo=tz)
    )
    
# Converts datetime into a human-readable 12-hour time
def _fmt(dt):
    return f"{dt.hour % 12 or 12}:{dt.minute:02d} {'AM' if dt.hour < 12 else 'PM'}"
    
# check if slot is free
def is_slot_free(start, duration_min, busy, hours_cfg, tz, now, policies, granularity=30):
    """Return (ok, reason). `busy` is a list of (start, end) tz-aware datetimes."""
    if start.tzinfo is None or now.tzinfo is None:
        raise ValueError("start and now must be timezone-aware")
    start = start.astimezone(tz)
    end = start + timedelta(minutes=duration_min)

    if start < now:
        return False, "That time has already passed."
    notice = policies.get("min_booking_notice_hours", 0)
    if start < now + timedelta(hours=notice):
        return False, f"We need at least {notice} hours notice for bookings."
    max_days = policies.get("max_days_ahead")
    if max_days is not None and start > now + timedelta(days=max_days):
        return False, f"We only book up to {max_days} days ahead."

    oc = open_close(start.date(), hours_cfg, tz)
    if oc is None:
        return False, f"The shop is closed on {start:%A}s."
    open_dt, close_dt = oc
    if start < open_dt:
        return False, f"We open at {_fmt(open_dt)} that day."
    if (start - open_dt).total_seconds() % (granularity * 60) != 0:
        return False, f"Start times must be on a {granularity}-minute mark."
    if end > close_dt:
        return False, f"That would run past closing time ({_fmt(close_dt)})."
    for b_start, b_end in busy:
        if overlaps(start, end, b_start, b_end):
            return False, "That time overlaps another appointment."
    return True, "ok"

# available slots on a particular day
def free_starts(d, duration_min, busy, hours_cfg, tz, now, policies, granularity=30):
    """All valid start datetimes on date d. Reuses is_slot_free so they never disagree."""
    oc = open_close(d, hours_cfg, tz)
    if oc is None:
        return []
    open_dt, close_dt = oc
    step = timedelta(minutes=granularity)
    dur = timedelta(minutes=duration_min)
    out, cur = [], open_dt
    while cur + dur <= close_dt:
        ok, _ = is_slot_free(cur, duration_min, busy, hours_cfg, tz, now, policies, granularity)
        if ok:
            out.append(cur)
        cur += step
    return out