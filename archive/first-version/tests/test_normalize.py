"""Checks that the output is right, not merely that the code ran.

Each of the four traps gets a test that fails if the trap is reintroduced.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from pipeline.normalize import clean_district, clean_issue_type, normalize, parse_local, status_group
from pipeline.report import build

KC = ZoneInfo("America/Chicago")
NOW = datetime(2026, 10, 22, 12, 0, tzinfo=KC)


def row(**fields):
    base = {
        "reported_issue": "1",
        "current_status": "resolved",
        "open_date_time": "2026-10-01T09:00:00.000",
        "issue_type": "Street Maintenance",
        "council_district": "3",
    }
    return {**base, **fields}


# Trap 1: one state, several spellings.
def test_status_spellings_merge():
    assert status_group("resolved") == status_group("Resolved") == "Resolved"
    assert status_group("received") == status_group("Received") == "Open"
    assert status_group("assigned") == status_group("Assigned") == "Open"
    assert status_group("closed") == "Resolved"
    assert status_group("something new") == "Other"


def test_status_spellings_count_together():
    requests = [
        normalize(row(current_status="resolved", days_to_close="2"), KC, NOW),
        normalize(row(current_status="Resolved", days_to_close="4"), KC, NOW),
    ]
    summary = dict(build(requests, NOW, NOW, NOW)["Summary"])
    assert summary["Resolved"] == 2


# Trap 2: days_to_close on an open row is age, not time to fix.
def test_open_rows_stay_out_of_days_to_resolve():
    requests = [
        normalize(row(current_status="resolved", days_to_close="2"), KC, NOW),
        normalize(row(current_status="received", days_to_close="300",
                      open_date_time="2025-12-26T12:00:00.000"), KC, NOW),
    ]
    summary = dict(build(requests, NOW, NOW, NOW)["Summary"])
    assert summary["Average days to resolve"] == 2
    assert summary["Average days open (still open)"] == 300


def test_open_age_comes_from_timestamp_not_stale_column():
    r = normalize(row(current_status="new", days_to_close="0",
                      open_date_time="2026-10-12T12:00:00.000"), KC, NOW)
    assert r.days_to_resolve is None
    assert r.open_age_days == 10


def test_negative_days_to_close_is_dropped():
    r = normalize(row(days_to_close="-7"), KC, NOW)
    assert r.days_to_resolve is None


# Trap 3: a resolved date on a canceled request does not make it resolved.
def test_canceled_with_resolved_date_is_not_resolved():
    r = normalize(row(current_status="canceled", resolved_date="2026-10-02T09:00:00.000",
                      days_to_close="1"), KC, NOW)
    assert r.status_group == "Canceled"
    assert r.days_to_resolve is None
    summary = dict(build([r], NOW, NOW, NOW)["Summary"])
    assert summary["Resolved"] == 0
    assert summary["Canceled"] == 1


# Trap 4: naive timestamps are Kansas City time, not UTC.
def test_naive_timestamp_is_kansas_city_time():
    opened = parse_local("2026-10-19T08:51:00.000", KC)
    assert opened.astimezone(timezone.utc) == datetime(2026, 10, 19, 13, 51, tzinfo=timezone.utc)


def test_open_age_is_right_when_clock_is_utc():
    # Opened 20:00 local on the 20th; 'now' is 00:30 UTC on the 22nd, which is
    # 19:30 local on the 21st: 23.5 hours. Read as UTC it would be 28.5 hours.
    now_utc = datetime(2026, 10, 22, 0, 30, tzinfo=timezone.utc)
    r = normalize(row(current_status="new", open_date_time="2026-10-20T20:00:00.000"), KC, now_utc)
    assert r.open_age_days == 0


def test_issue_type_cleanup():
    assert clean_issue_type("Trash  Recycling  Bulky Services") == "Trash / Recycling / Bulky Services"
    assert clean_issue_type("Trash / Recycling / Bulky Services") == "Trash / Recycling / Bulky Services"
    assert clean_issue_type("A Pothole") == "Pothole"
    assert clean_issue_type("Tents/Sleeping Structures") == "Tents or Sleeping Structures"
    assert clean_issue_type("Animal Services") == "Animal Services"


def test_missing_district_is_kept_as_unknown():
    assert clean_district(None) == "Unknown"
    assert clean_district("") == "Unknown"
    assert clean_district("4") == "4"
    requests = [normalize(row(council_district=None), KC, NOW), normalize(row(), KC, NOW)]
    districts = build(requests, NOW, NOW, NOW)["By district"]
    assert [d[0] for d in districts[1:]] == ["3", "Unknown"]
    assert sum(d[1] for d in districts[1:]) == 2
