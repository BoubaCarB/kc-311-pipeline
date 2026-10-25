"""Entry point: one command, start to finish.

    python -m pipeline.run              # fetch, save files, write the Sheet
    python -m pipeline.run --no-sheet   # fetch and save files only

Fetch the reporting window, keep the raw rows on disk, normalize, write
the cleaned rows and the report tables to disk, then to the Sheet.
Called the same way by a human, by cron, and by Actions.
"""

import argparse
import calendar
import csv
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from pipeline import config, fetch, normalize, report, sheets


def months_back(moment: datetime, months: int) -> datetime:
    """Same day `months` earlier, clamped to the month's length (Feb 29 -> 28), at midnight."""
    year, month = divmod(moment.year * 12 + moment.month - 1 - months, 12)
    month += 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return datetime(year, month, day, tzinfo=moment.tzinfo)


def write_csv(path: Path, rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)


def write_clean(path: Path, requests: list[normalize.Request]) -> None:
    fmt = "%Y-%m-%d %H:%M"
    rows = []
    for r in requests:
        row = asdict(r)
        row["opened"] = r.opened.strftime(fmt)
        row["resolved_at"] = r.resolved_at.strftime(fmt) if r.resolved_at else ""
        rows.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else [])
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Kansas City 311 report")
    parser.add_argument("--no-sheet", action="store_true", help="skip writing to Google Sheets")
    args = parser.parse_args()

    settings = config.load()
    now = datetime.now(settings.source_tz)
    window_start = months_back(now, settings.window_months)
    # Whole months on disk, exact window in the report; see fetch.py.
    fetch_start = window_start.replace(day=1)

    print(f"Fetching requests opened since {fetch_start:%Y-%m-%d}")
    raw = fetch.fetch_since(settings, fetch_start.replace(tzinfo=None))
    files = fetch.save_raw(raw, settings.data_dir / "raw")
    print(f"Saved raw data: {len(files)} monthly files in {settings.data_dir / 'raw'}")

    requests = [normalize.normalize(row, settings.source_tz, now) for row in raw]
    requests = [r for r in requests if r.opened >= window_start]
    requests.sort(key=lambda r: r.opened)
    write_clean(settings.data_dir / "clean" / "requests.csv", requests)
    print(f"Saved {len(requests):,} cleaned requests from {window_start:%Y-%m-%d}")

    tabs = report.build(requests, window_start, now, now, fetch.yearly_counts(settings))
    for title, rows in tabs.items():
        slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
        write_csv(settings.data_dir / "report" / f"{slug}.csv", rows)
    print(f"Saved report tables in {settings.data_dir / 'report'}")

    if args.no_sheet:
        print("Skipped Google Sheets (--no-sheet)")
    elif not settings.sheet_id:
        print("Skipped Google Sheets (GOOGLE_SHEET_ID is not set)")
    else:
        url = sheets.write_report(settings, tabs)
        print(f"Updated Google Sheet: {url}")


if __name__ == "__main__":
    main()
