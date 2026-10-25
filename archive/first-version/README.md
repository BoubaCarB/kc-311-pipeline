# KC 311 Pipeline

A job that pulls Kansas City's 311 service requests from the city's open
data API, reconciles the inconsistencies in them, and reports the result
to a Google Sheet that a non-engineer can open.

Not real time — the city publishes in batches.

## Why this data

Kansas City's 311 line is the city's non-emergency number: a resident
reports a pothole, a dead streetlight, illegal dumping. One row per report.

- Source: `https://data.kcmo.org/resource/d4px-6rwg.json` (Socrata SODA API;
  browse it at https://data.kcmo.org/d/d4px-6rwg)
- 843,661 rows going back to February 2021; no API key needed for modest use
- The catalog says weekly, but in practice the newest row is a couple of
  days old

The report covers the last 12 months: about 157,000 requests.

## The interesting part

A naive version of this gets all four of the following wrong and still
produces a report that looks fine. Figures are for the 12-month window.

**Status is six states wearing nine names.** `resolved` appears 105,590
times and `Resolved` 20,529 more; `received` 13,577 and `Received` 306;
`assigned` 1,470 and `Assigned` 180. Group by the raw column and every
count is wrong.

**`days_to_close` means two different things.** On a closed request it is
how long the fix took. On an open one it is how long the request has been
sitting. Average the column as-is and the backlog improves the number,
because the oldest unresolved requests get counted as the fastest closures.

**Canceled requests carry a resolved date.** All 10,046 canceled rows have
`resolved_date` set, exactly as the genuinely resolved ones do. Having a
resolved date is not having been fixed. Canceled is reported as its own
outcome, and the Summary tab says so.

**Timestamps have no timezone.** `2026-10-19T08:51:00.000` — no `Z`, no
offset. Naive local time. This is the trap most likely to yield numbers
that look plausible and are hours wrong.

Smaller ones: `issue_type` splits one category across names
(`Trash  Recycling  Bulky Services`, with double spaces where the slashes
were stripped, alongside `Trash / Recycling / Bulky Services`), and has a
leading article (`A Pothole`). About 5% of rows (8,149) have no council
district; they land in an "Unknown" bucket rather than being dropped. A
few resolved rows have a negative `days_to_close` and are left out of the
averages.

Every one of these has a test in `tests/test_normalize.py` that fails if
the trap comes back.

## What the Sheet shows

| Tab | Contents |
| --- | --- |
| Highlights | The report in a dozen plain-English sentences: what is reported most, where, how fast it gets fixed, what is stuck |
| Summary | Report period, how fresh the city's data is, totals by outcome, median and average days to resolve, average age of open requests, and notes on how things were counted |
| By category | The same figures for each issue type, largest first |
| By district | Council districts 1–6, plus Unknown, with each one's most reported issue |
| By area (ZIP) | The same per ZIP code, busiest first (the ZIP is read from the address) |
| By department | The same per city work group |
| Trends by year | Every year since 2021, counted by the API itself, so it needs no raw download |
| Trends by month | Month by month; the two edge months are marked partial |
| Oldest open | The 500 requests that have waited longest |
| Repeat addresses | Addresses reported 10 or more times, with the top issue and its share |
| How people report | Phone, apps, web and the rest, with how fast each gets resolved |
| When people report | Requests by day of week and by hour |

Each run rebuilds the tabs from scratch. Two things to read with care:
recent months look faster to resolve because their slow requests are still
open, and some repeat addresses are city buildings where staff log calls
(City Hall, 414 E 12th St, is mostly "Administration or Questions"), not
problem spots. Both are noted in the Sheet.

## What is saved in the project

| Folder | Contents |
| --- | --- |
| `data/raw/` | The API's rows exactly as returned, as JSON, a folder per year and a file per month (`2026/2026-10.json`). Kept on this computer only, not uploaded. |
| `data/clean/requests.csv` | Every request in the window after cleaning |
| `data/report/` | Every report tab as CSV |

Each run rewrites the months in the 12-month window; a new year gets its
folder automatically. To download every month since 2021 (about 840,000
rows, close to 1 GB), run `python -m pipeline.backfill` once. A month that
ages out of the window keeps its file as a snapshot: requests in it that
change status later are not updated there.

## Running it

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # then fill in GOOGLE_SHEET_ID

.venv/bin/python -m pipeline.run              # fetch, save, write the Sheet
.venv/bin/python -m pipeline.run --no-sheet   # fetch and save files only
.venv/bin/python -m pytest
```

Writing to the Sheet needs a Google service account: create one in a
Google Cloud project with the Sheets and Drive APIs enabled, save its JSON
key as `service-account.json` in this folder, and share the Sheet with the
account's email as Editor. A run takes under a minute.

## How it runs

```
pipeline.run
  -> Kansas City 311 open data API   (fetch.py; paginated, no key)
  -> data/raw/                       (raw copy, per month)
  -> reconcile                       (normalize.py; the traps above)
  -> count                           (report.py)
  -> data/clean/, data/report/       (CSV)
  -> Google Sheets                   (sheets.py; service account)
```

Every run refetches the whole window rather than only what changed, since
an old request can change status at any time; nothing is kept between
runs. Configuration is entirely environment variables, so the same
command runs on a laptop and on a scheduler.

## Status

Working end to end on a laptop, run by hand.

| Piece | State |
| --- | --- |
| `pipeline/` | done |
| `tests/` | 17 tests, passing |
| Hourly schedule | not set up yet |

Decisions and their reasons are in `docs/decisions.md`.
