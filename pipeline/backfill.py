"""Download the whole dataset into data/raw/, once.

    python -m pipeline.backfill

The regular run only refreshes the last 12 months. This fills in every
month back to the first report, one month at a time so the full ~840,000
rows never have to sit in memory together. Safe to run again: each month's
file is simply rewritten with the city's current version of it.
"""

from datetime import datetime

from pipeline import config, fetch


def next_month(moment: datetime) -> datetime:
    return moment.replace(year=moment.year + moment.month // 12, month=moment.month % 12 + 1)


def main() -> None:
    settings = config.load()
    raw_dir = settings.data_dir / "raw"
    month = fetch.first_report(settings).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = datetime.now(settings.source_tz).replace(tzinfo=None)
    total = 0
    while month <= end:
        print(f"{month:%Y-%m}")
        rows = fetch.fetch_since(settings, month, next_month(month))
        fetch.save_raw(rows, raw_dir)
        total += len(rows)
        month = next_month(month)
    print(f"Saved {total:,} rows in {raw_dir}")


if __name__ == "__main__":
    main()
