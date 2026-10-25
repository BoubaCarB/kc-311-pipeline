"""Pull service requests from the Socrata SODA API, and keep a raw copy.

Pages with $limit / $offset under a stable $order. Each run asks for every
request opened since the start of the reporting window, so status changes
on older requests are picked up too; there is no state between runs.

The raw rows are saved as the JSON the API returned, one file per month
of `open_date_time`, in a folder per year: data/raw/2026/2026-10.json.
A new year gets its folder the first time a row from it arrives. The fetch
starts on the 1st of the window's first month, so every month file written
is complete: a file that later falls out of the window is left behind as a
finished snapshot, never truncated.
"""

import json
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import requests

from pipeline.config import Settings

PAGE_SIZE = 50_000
TIMEOUT_SECONDS = 120
RETRIES = 4


def _timestamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%S")


def fetch_since(settings: Settings, since: datetime, until: datetime | None = None) -> list[dict]:
    """Every request opened at or after `since` and before `until` (naive local time, like the source)."""
    where = f"open_date_time >= '{_timestamp(since)}'"
    if until:
        where += f" AND open_date_time < '{_timestamp(until)}'"
    rows: list[dict] = []
    while True:
        params = {
            "$where": where,
            "$order": ":id",
            "$limit": PAGE_SIZE,
            "$offset": len(rows),
        }
        page = _get(settings, params)
        rows.extend(page)
        print(f"  fetched {len(rows):,} rows")
        if len(page) < PAGE_SIZE:
            return rows


def first_report(settings: Settings) -> datetime:
    """When the dataset begins, so a full download knows where to start."""
    result = _get(settings, {"$select": "min(open_date_time) AS first"})
    return datetime.fromisoformat(result[0]["first"])


def _get(settings: Settings, params: dict) -> list[dict]:
    headers = {"X-App-Token": settings.app_token} if settings.app_token else {}
    for attempt in range(1, RETRIES + 1):
        try:
            resp = requests.get(settings.dataset_url, params=params, headers=headers, timeout=TIMEOUT_SECONDS)
            if resp.status_code < 500 and resp.status_code != 429:
                resp.raise_for_status()
                return resp.json()
            error = f"HTTP {resp.status_code}"
        except (requests.ConnectionError, requests.Timeout) as exc:
            error = str(exc)
        if attempt == RETRIES:
            raise RuntimeError(f"311 API failed after {RETRIES} attempts: {error}")
        wait = 5 * attempt
        print(f"  API error ({error}), retrying in {wait}s")
        time.sleep(wait)


def save_raw(rows: list[dict], raw_dir: Path) -> list[Path]:
    """Write rows as returned by the API, one JSON file per month opened. Returns the files written."""
    by_month: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_month[row.get("open_date_time", "unknown")[:7]].append(row)

    written = []
    for month, month_rows in sorted(by_month.items()):
        path = raw_dir / month[:4] / f"{month}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        # Pretty-printed, one field per line, so the file reads top to bottom.
        with path.open("w", encoding="utf-8") as f:
            json.dump(month_rows, f, indent=2, ensure_ascii=False)
            f.write("\n")
        written.append(path)
    return written
