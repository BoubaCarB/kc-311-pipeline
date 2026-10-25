# KC 311 Pipeline

A job that pulls Kansas City's 311 service requests from the city's open
data API and reports on them in a Google Sheet that a non-engineer can
open.

> Built step by step. Sections fill in as the pieces land. The first full
> attempt is kept in `archive/first-version/` for comparison.

## The data

Kansas City's 311 line is the city's non-emergency number: a resident
reports a pothole, a dead streetlight, illegal dumping. One row per report.

- Source: `https://data.kcmo.org/resource/d4px-6rwg.json` (Socrata SODA API;
  browse it at https://data.kcmo.org/d/d4px-6rwg)
- 843,661 reports from February 2021 on; no API key needed for modest use
- The newest report is usually a few days old

## What we found so far

Before cleaning anything, every report was scanned for inconsistencies.
The data has more problems than expected, and several got worse, not better:

- **The same value is spelled several ways.** `resolved` and `Resolved`
  are counted as different statuses: 12 spellings for 8 real statuses.
  Category names changed mid-stream (`A Pothole`, `Trash  Recycling  Bulky
  Services` with double spaces).
- **Resolved dates never have a time.** All 793,994 are stamped midnight,
  so many reports look resolved before they were opened.
- **Canceled reports carry a resolved date.** Since April 2024, every one
  of them does.
- **Most of the spelling problems start or jump in 2024**, which suggests
  something changed in how the city's system records reports. The address
  problems mostly date from 2021, the system's first year, and were fixed.

Full findings, with counts by year: [docs/data-quality.md](docs/data-quality.md).

## What is saved

`data/raw/` holds the API's rows exactly as returned, as pretty-printed
JSON: a folder per year, a file per month opened (`2026/2026-10.json`).
It stays on this computer and is not uploaded (about 740 MB).

## Running it

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env

.venv/bin/python -m pipeline.backfill   # once: every month since 2021
.venv/bin/python -m pipeline.run        # refresh the last 12 months

.venv/bin/python analysis/data_quality.py           # list every data problem
.venv/bin/python analysis/data_quality_by_year.py   # count them by year
```

## Status

| Piece | State |
| --- | --- |
| `pipeline/fetch.py` | done: API pull, raw JSON by year and month |
| `pipeline/backfill.py` | done: full history download |
| `pipeline/config.py` | done |
| `pipeline/sheets.py` | connection to the Sheet works; nothing written yet |
| `analysis/` | done: data-quality scan, see [docs/data-quality.md](docs/data-quality.md) |
| Cleaning | next, starting with `current_status` |
| Report | not started |
| Hourly schedule | not started |
