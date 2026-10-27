# Decisions

One short entry per decision, with the reason. Written down because in an
interview the reason is the interesting half.

## Decided

- **Output is a Google Sheet, not a web page.** Non-technical people can
  open a spreadsheet without being taught anything. A page is a larger
  build; deferred.
- **Hourly, not more often.** GitHub Actions enforces a 5-minute floor on
  scheduled workflows and delays them by tens of minutes under load. The
  city publishes in batches anyway, so a faster cadence would buy nothing.
- **Config comes from the environment.** Same command on a laptop and in
  Actions.
- **Writing to the Sheet uses a service account.** The job will run on a
  schedule with nobody there to log in, and the account can reach only the
  one Sheet shared with it.
- **Raw data is saved as the JSON the API returned.** CSV is about 40%
  smaller, but turns every value into text and flattens nested fields; the
  raw copy should be what the city actually sent. Pretty-printed so it
  reads top to bottom (about 20% bigger again).
- **Raw files are a folder per year, a file per month, and stay local.**
  A year in one file would be ~170 MB, over GitHub's 100 MB file limit.
  The full history is close to 1 GB, and an hourly job committing fresh
  copies would grow the repository's history by gigabytes, so `data/raw/`
  is gitignored; the scheduled run will work in memory.
- **The regular run refreshes the last 12 months; the full history is a
  one-time backfill.** An old request can change status at any time, so
  the recent window is refetched whole. The fetch starts on the 1st of the
  window's first month, so month files are always complete.

- **The Sheet has three tabs: Summary, Categories, Reports.** Enough to
  see what's being reported and what's most recent. One Reports tab with
  a filter instead of a tab per category: there are about 50 categories.
- **The Sheet covers the last 12 months.** A Google Sheet holds at most 10
  million cells; every report since 2021 would need about 15 million.
- **Only the problems the three tabs need get fixed.** The rest are
  documented in `data-quality.md` and left as the city sends them, so the
  cleaning stays small and every fix has a reason. The list and its
  progress are in `cleaning-plan.md`.

## Open

- How each problem in `cleaning-plan.md` gets fixed.
- How the schedule survives GitHub disabling workflows after 60 days of
  repository inactivity.
