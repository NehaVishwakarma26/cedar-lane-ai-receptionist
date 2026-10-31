import re


def normalize_phone(raw):
    """-> E.164 string (+91XXXXXXXXXX for Indian mobiles) or None."""
    if not raw:
        return None
    raw = str(raw).strip()
    digits = re.sub(r"\D", "", raw)

    if raw.startswith("+"):                      # explicit country code
        return "+" + digits if 8 <= len(digits) <= 15 else None

    if digits.startswith("0091"):                # 0091 98765 43210
        digits = digits[4:]
    elif len(digits) == 12 and digits.startswith("91"):   # 91 98765 43210
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):    # 098765 43210
        digits = digits[1:]

    if len(digits) == 10 and digits[0] in "6789":         # Indian mobile
        return "+91" + digits
    return None

def strip_think(text):
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL)
    text = re.sub(r"<think>.*", "", text, flags=re.DOTALL)  # unclosed block
    return text.strip()


def now_local():
    """Everything calls this (as utils.now_local()) so tests can monkeypatch it."""
    return datetime.now(config.TZ)


def parse_iso_local(s):
    dt = datetime.fromisoformat(str(s).strip().replace("Z", "+00:00"))
    return dt.replace(tzinfo=config.TZ) if dt.tzinfo is None else dt.astimezone(config.TZ)


def fmt_time(dt):
    return f"{dt.hour % 12 or 12}:{dt.minute:02d} {'AM' if dt.hour < 12 else 'PM'}"


def fmt_date(d):
    return f"{d:%a %b} {d.day}"


def fmt_human(dt):
    return f"{fmt_date(dt)}, {fmt_time(dt)}"


def fmt_hhmm(s):
    """'08:00' -> '8:00 AM'"""
    h, m = s.split(":")
    h, m = int(h), int(m)
    return f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"
