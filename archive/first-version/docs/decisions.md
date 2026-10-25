# Decisions

One short entry per decision, with the reason. Written down because in an
interview the reason is the interesting half.

## Decided

- **Output is a Google Sheet, not a web page.** Non-technical people can
  open a spreadsheet without being taught anything. A page is a larger
  build; deferred.
- **Hourly, not more often.** GitHub Actions enforces a 5-minute floor on
  scheduled workflows and delays them by tens of minutes under load. The
  city publishes in batches anyway, so a faster cadence would buy nothing
  and the README would be making a claim it can't keep.
- **Config comes from the environment.** Same command on a laptop and in
  Actions.
- **Eleven tabs, led by Highlights.** The tables answer where, what, how
  fast, and what is stuck; the Highlights tab says it in sentences, because
  the point is to make sense of the data, not only to count it. Summary,
  By category and By district came first; By area (ZIP), By department,
  Trends by month, Oldest open, Repeat addresses, How people report and
  When people report were added on top.
- **Area means ZIP code, read from the address.** 98% of addresses end in
  one, and it needs no extra data source or map API. Neighborhoods would
  need boundary data; a map can come later from the latitude/longitude
  already in the clean file.
- **Oldest open is capped at 500 rows, repeat addresses at 10+ reports.**
  Enough to act on without making the Sheet slow to open.
- **Repeat addresses are shown with their top issue and its share.** Some
  are city buildings where staff log calls, not problem spots; the share
  makes that visible instead of silently filtering them.
- **Partial months are labelled, not dropped.** The window starts and ends
  mid-month; unlabelled, the edges read as sudden drops.
- **The report covers the last 12 months.** Recent enough to describe how
  the city is doing now; about 157,000 requests, so one run takes under a
  minute.
- **Each run rebuilds the Sheet from scratch; nothing persists between
  runs.** An old request can change status at any time, so a refetch of
  the whole window is the simple way to stay correct. No watermark, so no
  state to keep alive on a CI runner.
- **The raw pull is kept on disk, in the project.** One JSON file per month in
  `data/raw/`, exactly as the API returned it, alongside the cleaned rows
  and the report tables. The data is public, and having the input next to
  the output makes every number checkable. Monthly files keep each one
  small (under 15 MB). The fetch starts on the 1st of the window's first
  month, so a month file is always complete; months that age out of the
  window stay as frozen snapshots.
- **Canceled requests do not count as resolved.** They carry a resolved
  date, but nothing was fixed. They are reported as their own column, and
  the Summary tab says so.
- **Referred is its own outcome.** Handed to another agency: not fixed by
  the city, not waiting in its queue. Counted as neither resolved nor open.
- **Open age is recomputed from the timestamp, not read from
  `days_to_close`.** The published value is only as fresh as the city's
  last refresh of the row.
- **Negative `days_to_close` is dropped from the averages.** A few rows
  close before they open; that is a data error, not a fast fix.
- **Unrecognized statuses go to an "Other" bucket** and are flagged on the
  Summary tab, rather than crashing the run or vanishing.
- **The Sheet is written in a few batched requests.** One call per
  formatting step per tab would be over 60 writes, the Sheets API's
  per-minute quota.

- **Raw files are a folder per year, a file per month, and stay local.**
  A year in one file would be ~170 MB, over GitHub's 100 MB file limit.
  The full history is close to 1 GB, and an hourly job committing fresh
  copies would grow the repository's history by gigabytes, so `data/raw/`
  is gitignored; the scheduled run will work in memory.
- **The multi-year trend is counted by the API, not from raw rows.** One
  grouped query returns a few hundred bytes for every year since 2021,
  so the yearly tab costs nothing to refresh. Statuses are grouped raw and
  merged in Python, by the same rules as everything else.

## Open

- How the schedule survives GitHub disabling workflows after 60 days of
  repository inactivity.
