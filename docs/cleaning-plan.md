# Cleaning plan

What gets fixed, why, and how. The problems themselves are described in
[data-quality.md](data-quality.md); this file tracks what is done about them.
Updated as each decision is made.

## Goal...

Anyone can open one Google Sheet and see what Kansas City residents are
reporting, by category, and what's most recent.

## What the Sheet will show

| Tab | What it shows |
| --- | --- |
| **1. Summary** | A few key numbers: total reports, how many are open or resolved, the most recent report |
| **2. Categories** | Every category with its number of reports, biggest first |
| **3. Reports** | Every report from the last 12 months, cleaned up, newest first, filterable by category |

Only the last 12 months go in the Sheet: a Google Sheet holds at most 10
million cells, and all reports since 2021 would need about 15 million.

## Problems being fixed

Only the problems these three tabs need. Counts are for all reports since
2021, from [data-quality.md](data-quality.md).

| # | Problem | How many | Needed for | Decision | Status |
| --- | --- | --- | --- | --- | --- |
| 1 | Status spelled several ways (`resolved` / `Resolved`): 12 spellings, 8 real statuses | 61,730 capitalized | Open vs resolved counts | To decide | **Next** |
| 2 | Canceled reports that have a resolved date | 28,990 | Open vs resolved counts | To decide | Not started |
| 3 | Category spelled several ways (`Trash  Recycling  Bulky Services`, `A Pothole`) | 81,645 | Categories tab | To decide | Not started |
| 4 | Sub-type spelled several ways (`Spot Clean Up` / `Spot Cleanup`, `--`) | 14 pairs | Reports tab | To decide | Not started |
| 5 | Resolved dates have no time (always midnight) | 793,994 | Reports tab | To decide | Not started |
| 6 | Timestamps have no timezone | All rows | Reports tab, most recent report | To decide | Not started |

## Not fixing for now

Not needed for the three tabs. Left exactly as the city sends them, and
revisited if the Sheet grows.

| Problem | Why it can wait |
| --- | --- |
| Missing or misspelled addresses, no ZIP, coordinates outside Kansas City | The Sheet doesn't group by area yet |
| No council district | Same |
| `days_to_close` unreliable; resolved before opened; 1969 placeholder dates | The Sheet doesn't measure how fast reports are fixed yet |
| `last_updated` before opened | Not shown |
| `additional_questions` badly formatted | Not shown |
| `Web` vs `WEB RAI`, `App` vs iOS/Android | The Sheet doesn't group by report source |
| `workorder_` empty for 41% | Not an error |

## Rules for every fix

1. **Never change the raw files.** Cleaning makes a new version; `data/raw/` stays as the city sent it.
2. **Every fix is an agreed rule**, recorded in the table above with the reason.
3. **Every fix is counted**, so the Sheet can say how much was changed.
