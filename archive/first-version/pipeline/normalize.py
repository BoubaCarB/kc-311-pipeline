"""Turn the raw rows into rows that can be counted.

This is where the four known traps in the source data get handled:

  1. `current_status` arrives in mixed case  — nine spellings of six states.
  2. `days_to_close` means time-to-close on a closed row and age-so-far on
     an open one. Averaging the raw column flatters the backlog.
  3. Cancelled requests carry a `resolved_date`. Having a resolved date is
     not the same as having been fixed.
  4. Timestamps have no timezone or offset. They are naive local time.

Also: `issue_type` has double spaces where punctuation was stripped, and
leading articles ("A Pothole"). Rows with no council district need a
bucket to land in rather than being dropped. The ZIP code is pulled out of
the address, since there is no ZIP column.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

# Trap 1 and 3. Keys are lowercased before lookup, so "Resolved" and
# "resolved" land together. Canceled is its own outcome, never Resolved,
# whatever `resolved_date` says. Referred means handed to another agency:
# not fixed by the city, but not waiting in its queue either.
STATUS_GROUPS = {
    "new": "Open",
    "received": "Open",
    "assigned": "Open",
    "active": "Open",
    "resolved": "Resolved",
    "closed": "Resolved",
    "canceled": "Canceled",
    "cancelled": "Canceled",
    "referred": "Referred",
}
GROUPS = ("Resolved", "Open", "Referred", "Canceled", "Other")

# Same category under two names, after whitespace and articles are cleaned.
ISSUE_TYPE_ALIASES = {
    "Trash Recycling Bulky Services": "Trash / Recycling / Bulky Services",
    "Tents/Sleeping Structures": "Tents or Sleeping Structures",
}
LEADING_ARTICLE = re.compile(r"^(a|an|the)\s+", re.IGNORECASE)

DISTRICTS = {"1", "2", "3", "4", "5", "6"}
UNKNOWN_DISTRICT = "Unknown"
UNKNOWN_ZIP = "Unknown"
# Kansas City ZIPs all start with 6; take the last one in the address.
ZIP = re.compile(r"\b(6\d{4})\b")


@dataclass(frozen=True)
class Request:
    id: str
    opened: datetime  # timezone-aware
    resolved_at: datetime | None
    status: str
    status_group: str
    issue_type: str
    issue_sub_type: str
    department: str
    district: str
    zip: str
    source: str
    address: str
    latitude: str
    longitude: str
    days_to_resolve: int | None  # Resolved rows only
    open_age_days: int | None  # Open rows only, measured against `now`


def parse_local(value: str | None, tz: ZoneInfo) -> datetime | None:
    """Trap 4: the source writes naive local time. Attach the zone, don't convert."""
    if not value:
        return None
    return datetime.fromisoformat(value).replace(tzinfo=tz)


def status_group(status: str | None) -> str:
    return STATUS_GROUPS.get((status or "").strip().lower(), "Other")


def clean_text(value: str | None) -> str:
    return " ".join((value or "").split())


def clean_issue_type(value: str | None) -> str:
    name = LEADING_ARTICLE.sub("", clean_text(value))
    name = name[:1].upper() + name[1:]
    return ISSUE_TYPE_ALIASES.get(name, name) or "Unspecified"


def clean_district(value: str | None) -> str:
    value = clean_text(value)
    return value if value in DISTRICTS else UNKNOWN_DISTRICT


def extract_zip(address: str) -> str:
    found = ZIP.findall(address)
    return found[-1] if found else UNKNOWN_ZIP


def normalize(raw: dict, tz: ZoneInfo, now: datetime) -> Request:
    opened = parse_local(raw["open_date_time"], tz)
    group = status_group(raw.get("current_status"))

    # Trap 2: the one column carries two measures. Split it by status, and
    # recompute the open age from the timestamp, because the published value
    # was frozen whenever the city last refreshed the row.
    days_to_resolve = None
    if group == "Resolved" and raw.get("days_to_close") not in (None, ""):
        days = int(float(raw["days_to_close"]))
        # A handful of rows close before they open; leave them out of the
        # average rather than let them pull it down.
        days_to_resolve = days if days >= 0 else None
    open_age_days = (now - opened).days if group == "Open" else None

    address = clean_text(raw.get("incident_address"))
    return Request(
        id=raw.get("reported_issue", ""),
        opened=opened,
        resolved_at=parse_local(raw.get("resolved_date"), tz),
        status=clean_text(raw.get("current_status")).lower(),
        status_group=group,
        issue_type=clean_issue_type(raw.get("issue_type")),
        issue_sub_type=clean_text(raw.get("issue_sub_type")),
        department=clean_text(raw.get("department_work_group")) or "Unspecified",
        district=clean_district(raw.get("council_district")),
        zip=extract_zip(address),
        source=clean_text(raw.get("report_source")) or "Unspecified",
        address=address,
        latitude=raw.get("latitude", ""),
        longitude=raw.get("longitude", ""),
        days_to_resolve=days_to_resolve,
        open_age_days=open_age_days,
    )
