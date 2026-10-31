"""Contact sheet tests using a local in-memory Google Sheets fake."""

from datetime import datetime, timezone

import sheets


class FakeValues:
    def __init__(self):
        self.rows = []
        self.appended = []
        self.updated = []

    def get(self, **_kwargs):
        return FakeRequest({"values": self.rows})

    def append(self, **kwargs):
        self.appended.append(kwargs)
        self.rows.append(kwargs["body"]["values"][0])
        return FakeRequest({})

    def update(self, **kwargs):
        self.updated.append(kwargs)
        row_number = int(kwargs["range"].split("A")[1].split(":")[0])
        self.rows[row_number - 2] = kwargs["body"]["values"][0]
        return FakeRequest({})


class FakeRequest:
    def __init__(self, result):
        self.result = result

    def execute(self):
        return self.result


def test_anonymous_contact_is_created_then_updated_by_session_id(monkeypatch):
    fake = FakeValues()
    monkeypatch.setattr(sheets, "get_values", lambda: fake)
    now = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)

    created = sheets.upsert_contact(
        name=None,
        category="other",
        summary="Asked about policies",
        now=now,
        session_id="anonymous-123",
    )

    assert created == "created"
    assert fake.appended[0]["range"] == "Contacts!A:J"
    assert fake.rows[0][0] == ""
    assert fake.rows[0][9] == "anonymous-123"

    updated = sheets.upsert_contact(
        name="A Customer",
        category="booking",
        summary="Asked about booking",
        now=now,
        session_id="anonymous-123",
    )

    assert updated == "updated"
    assert len(fake.appended) == 1
    assert fake.updated[0]["range"] == "Contacts!A2:J2"
    assert fake.rows[0][1] == "A Customer"
    # Repeated save within the same conversation must not inflate call_count.
    assert fake.rows[0][5] == 1
    assert fake.rows[0][9] == "anonymous-123"


def test_call_log_is_updated_by_session_id_instead_of_duplicated(monkeypatch):
    fake = FakeValues()
    monkeypatch.setattr(sheets, "get_values", lambda: fake)

    sheets.append_call_log("2026-10-31T12:00:00+00:00", "session-1", None, None,
                           "other", "first turn", "resolved")
    sheets.append_call_log("2026-10-31T12:01:00+00:00", "session-1", None, None,
                           "other", "updated summary", "resolved")

    assert len(fake.appended) == 1
    assert len(fake.updated) == 1
    assert fake.rows[0][5] == "updated summary"
