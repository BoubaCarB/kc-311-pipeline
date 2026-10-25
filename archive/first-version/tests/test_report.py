"""Checks on the report tabs beyond the four traps."""

from datetime import datetime
from zoneinfo import ZoneInfo

from pipeline.normalize import extract_zip, normalize
from pipeline.report import REPEAT_ADDRESS_MIN, build

KC = ZoneInfo("America/Chicago")
NOW = datetime(2026, 10, 22, 12, 0, tzinfo=KC)
START = datetime(2025, 10, 22, tzinfo=KC)


def req(**fields):
    base = {
        "reported_issue": "1",
        "current_status": "resolved",
        "days_to_close": "2",
        "open_date_time": "2026-06-10T09:00:00.000",
        "issue_type": "Street Maintenance",
        "council_district": "3",
        "incident_address": "100 Main St Kansas City 64105",
        "report_source": "Phone Answered",
    }
    return normalize({**base, **fields}, KC, NOW)


def test_zip_comes_from_the_address():
    assert extract_zip("7906 N Forest Ave Kansas City 64118") == "64118"
    assert extract_zip("") == "Unknown"
    # A house number that looks like a ZIP is not the ZIP; the last one is.
    assert extract_zip("64130 E 63rd St Kansas City 64132") == "64132"


YEARLY = (
    [
        {"year": "2021", "current_status": "resolved", "reports": "80", "first": "2021-02-18T12:30:00.000", "last": "2021-12-31T23:00:00.000"},
        {"year": "2022", "current_status": "resolved", "reports": "70", "first": "2022-01-01T01:00:00.000", "last": "2022-12-31T23:00:00.000"},
        {"year": "2022", "current_status": "Resolved", "reports": "30", "first": "2022-01-02T01:00:00.000", "last": "2022-12-30T23:00:00.000"},
        {"year": "2022", "current_status": "canceled", "reports": "20", "first": "2022-01-03T01:00:00.000", "last": "2022-12-29T23:00:00.000"},
        {"year": "2023", "current_status": "resolved", "reports": "150", "first": "2023-01-01T01:00:00.000", "last": "2023-12-31T23:00:00.000"},
        {"year": "2026", "current_status": "new", "reports": "40", "first": "2026-01-01T01:00:00.000", "last": "2026-10-19T08:51:00.000"},
    ],
    [
        {"year": "2022", "current_status": "resolved", "rows": "70", "days": "140"},
        {"year": "2022", "current_status": "Resolved", "rows": "30", "days": "160"},
        # Canceled rows have days_to_close too; they must not move the average.
        {"year": "2022", "current_status": "canceled", "rows": "20", "days": "9000"},
    ],
)


def test_yearly_trend_merges_spellings_and_marks_partial_years():
    yearly = {row[0]: row for row in build([req()], START, NOW, NOW, YEARLY)["Trends by year"][1:]}
    assert yearly["2022"][1:6] == [120, 100, 0, 0, 20]
    assert yearly["2022"][6] == 3.0
    assert yearly["2021"][-1].startswith("Partial year: data starts Feb 18")
    assert yearly["2026"][-1].startswith("Partial year: through Oct 19")
    # No change against a partial year; +25% between two full ones.
    assert yearly["2022"][7] == "" and yearly["2023"][7] == "+25%"


def test_every_tab_is_built():
    tabs = build([req()], START, NOW, NOW, YEARLY)
    assert list(tabs) == [
        "Highlights", "Summary", "By category", "By district", "By area (ZIP)", "By department",
        "Trends by year", "Trends by month", "Oldest open", "Repeat addresses", "How people report", "When people report",
    ]
    for rows in tabs.values():
        assert rows and rows[0]


def test_edge_months_are_marked_partial():
    rows = [req(open_date_time="2025-10-25T09:00:00.000"), req(), req(open_date_time="2026-10-02T09:00:00.000")]
    trends = build(rows, START, NOW, NOW)["Trends by month"]
    notes = {row[0]: row[-1] for row in trends[1:]}
    assert notes == {"2025-10": "Partial month", "2026-06": "", "2026-10": "Partial month"}


def test_oldest_open_lists_longest_waiting_first():
    rows = [
        req(current_status="new", open_date_time="2026-10-01T09:00:00.000", reported_issue="recent"),
        req(current_status="received", open_date_time="2026-01-01T09:00:00.000", reported_issue="old"),
        req(current_status="resolved", open_date_time="2025-11-01T09:00:00.000", reported_issue="done"),
    ]
    oldest = build(rows, START, NOW, NOW)["Oldest open"]
    assert [row[-1] for row in oldest[1:]] == ["old", "recent"]


def test_repeat_addresses_need_the_minimum():
    busy = [req(incident_address="1 Busy St Kansas City 64130") for _ in range(REPEAT_ADDRESS_MIN)]
    quiet = [req(incident_address="2 Quiet St Kansas City 64130") for _ in range(REPEAT_ADDRESS_MIN - 1)]
    repeats = build(busy + quiet, START, NOW, NOW)["Repeat addresses"]
    assert [row[0] for row in repeats[1:]] == ["1 Busy St Kansas City 64130"]
    assert repeats[1][3] == REPEAT_ADDRESS_MIN


def test_weekdays_and_hours_add_up():
    rows = [req(), req(open_date_time="2026-06-13T22:00:00.000")]  # a Wednesday and a Saturday
    timing = build(rows, START, NOW, NOW)["When people report"]
    by_label = {row[0]: row[1] for row in timing if row[0]}
    assert by_label["Wednesday"] == 1 and by_label["Saturday"] == 1
    assert by_label["9 AM"] == 1 and by_label["10 PM"] == 1
