"""Entry point: one command, start to finish.

    python -m pipeline.run

For now: fetch the last 12 months and save the raw rows to data/raw/.
Cleaning and the report are built next, one step at a time.
Called the same way by a human, by cron, and by Actions.
"""

import calendar
from datetime import datetime

from pipeline import config, fetch


def months_back(moment: datetime, months: int) -> datetime:
    """Same day `months` earlier, clamped to the month's length (Feb 29 -> 28), at midnight."""
    year, month = divmod(moment.year * 12 + moment.month - 1 - months, 12)
    month += 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return datetime(year, month, day, tzinfo=moment.tzinfo)


def main() -> None:
    settings = config.load()
    now = datetime.now(settings.source_tz)
    # Whole months on disk; see fetch.py.
    fetch_start = months_back(now, settings.window_months).replace(day=1)

    print(f"Fetching requests opened since {fetch_start:%Y-%m-%d}")
    raw = fetch.fetch_since(settings, fetch_start.replace(tzinfo=None))
    files = fetch.save_raw(raw, settings.data_dir / "raw")
    print(f"Saved raw data: {len(files)} monthly files in {settings.data_dir / 'raw'}")


if __name__ == "__main__":
    main()
