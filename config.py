"""Loads .env + shop.yaml once. Fails loudly at import if the config is inconsistent."""
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from dotenv import load_dotenv

import slots

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

with open(ROOT / "shop.yaml", encoding="utf-8") as _f:
    _cfg = yaml.safe_load(_f)

SHOP = _cfg["shop"]
HOURS = _cfg["hours"]
SERVICES = _cfg["services"]
VEHICLES = _cfg["vehicles"]
PREP = _cfg["prep"]
POLICIES = _cfg["policies"]
GRANULARITY = int(SHOP["slot_granularity_min"])

TZ = ZoneInfo(os.getenv("SHOP_TZ") or SHOP["timezone"])
CALENDAR_ID = os.getenv("CALENDAR_ID", "primary")
SHEET_ID = os.getenv("SHEET_ID", "")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")


def _validate():
    if SHOP.get("bays", 1) != 1:
        raise NotImplementedError("slots.py only supports bays: 1")
    for key, svc in SERVICES.items():
        d = svc["duration_min"]
        if not isinstance(d, int) or d <= 0 or d % GRANULARITY:
            raise ValueError(f"service {key}: duration must be a positive multiple of {GRANULARITY}")
        if not isinstance(svc["price"], (int, float)):
            raise ValueError(f"service {key}: price must be a number")
    for day, rng in HOURS.items():
        if day not in slots.DAY_KEYS:
            raise ValueError(f"unknown day key {day!r} in hours")
        o, c = (slots.parse_hhmm(x) for x in rng)
        if o >= c:
            raise ValueError(f"hours for {day}: open must be before close")


_validate()
