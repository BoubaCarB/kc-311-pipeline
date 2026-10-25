# Data quality: what's inconsistent in the 311 data

A scan of every report in `data/raw/`: **843,661 reports**, February 18,
2021 to October 19, 2026, as downloaded on October 25, 2026. Nothing was
changed or fixed; this only records what is there.

**What's clean:** every report ID is unique (no duplicates), and every row
has an opened date.

---

## Part 1: The problems

### 1. Same thing, different spelling

| Field | Example | How many |
| --- | --- | --- |
| `current_status` | `resolved` (692,612) vs `Resolved` (60,858). Same for closed, received, assigned | 12 spellings, 8 real statuses |
| `issue_type` | `Trash / Recycling / Bulky Services` (90,966) vs `Trash  Recycling  Bulky Services` (57,921, double spaces where the slashes were removed) | 57,921 |
| `issue_type` | `A Pothole` ("A" in front) | 23,724 |
| `issue_sub_type` | `Dumping in a Right-of-Way` vs `Dumping in a Right of Way` | 1,159 |
| `issue_sub_type` | `Pole Damaged\| Down or Leaning` vs `Pole Damaged, Down or Leaning` | 2,551 vs 515 |
| `issue_sub_type` | `Spot Clean Up` vs `Spot Cleanup`, `Landbank` vs `Land Bank`, `Mayors Office` vs `Mayor's Office` | 14 pairs like this |
| `issue_sub_type` | `--` used as a value instead of blank | 2 |

### 2. Dates that don't make sense

| Problem | Example | How many |
| --- | --- | --- |
| **Resolved dates have no time.** Every one is midnight (`2021-04-20T00:00:00`) | Report 543564 | 793,994 (100% of resolved dates) |
| Because of that, the resolved time is **earlier than the opened time on the same day** | Opened `2021-03-09 13:53`, resolved `2021-03-09 00:00` | 93,453 |
| Resolved on an **earlier day** than opened | Opened Mar 22, resolved Mar 21 | 65 |
| **Placeholder date** `1969-12-31` used as a resolved date | Report 568065 | 52 |
| `last_updated` **before** the report was opened | Opened Mar 27, updated Mar 9 | 2,732 |
| **Timestamps have no timezone** | `2021-02-27T11:55:00.000` | All rows |

### 3. `days_to_close` is unreliable

| Problem | Example | How many |
| --- | --- | --- |
| On **open** reports it's how long the report has been waiting, not time to fix | 1,625 days on a report still "received" | 27,772 |
| **Disagrees with the two dates** by more than a day | Field says 0, dates are 1,110 days apart | 5,398 |
| **Negative values**, from the 1969 placeholder date | −18,718 days | 105 |

### 4. Status that contradicts the dates

| Problem | How many |
| --- | --- |
| **Canceled** reports that have a resolved date | 28,990 |
| Status "resolved" but **no resolved date** | 5 |

### 5. Addresses and locations

| Problem | Example | How many |
| --- | --- | --- |
| No address at all | | 21,663 (2.6%) |
| Address with **no ZIP code** | `660 E 63rd St Kansas City` | 8,615 |
| **Typos** or the city name missing | `Kansas Citt`, `9600 N Oak Trfy  64155` | 293 |
| Placeholder text instead of an address | `<null> <null> <null>` | included above |
| Extra spaces, inconsistent capitals | `6401  South Benton`, `1080 washington` | 75+ |
| **Coordinates far outside Kansas City** | One in Arizona, one in western Kansas | 8 |
| Coordinates but no address | | 47 |
| No council district | | 28,420 (3.4%) |

### 6. `additional_questions` is broken

Supposed to be structured data, but almost every value is badly formatted:
quotes are missing and `|` is used as a separator.

```
{What is the problem?":"Sinking"}"
{Type of Sign":"Load Zone Sign"|"Issue":"Missing"}"
```

748,315 rows (89% of all reports; 99% of those that have answers).

### 7. Not necessarily wrong, but unclear

- `report_source` has both `Web` (338) and `WEB RAI` (140,656), and `App` (66) next to `iOS` and `Android`. They could be the same thing or different channels.
- `issue_type` has both `Animals and Pets` and `Animal Services`.
- `workorder_` is empty for 41% of reports. Normal for reports never passed to another system, but worth knowing.

---

## Part 2: Getting better or worse?

Each problem counted by the year the report was opened. Shown as a share of
that year's reports, unless the row says otherwise, because years have
different numbers of reports.

**2021 and 2026 are partial years:** 2021 starts February 18, and 2026 runs
to October 19.

| Year | 2021* | 2022 | 2023 | 2024 | 2025 | 2026* |
| --- | --- | --- | --- | --- | --- | --- |
| Reports | 107,357 | 131,719 | 148,596 | 157,694 | 167,089 | 131,206 |

### The common problems (% of that year)

| Problem | 2021* | 2022 | 2023 | 2024 | 2025 | 2026* | Trend |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Status capitalized (`Resolved`) | 0.4% | 0.4% | 0.6% | 12.4% | 14.2% | 12.7% | **Worse from 2024** |
| Trash name with double spaces | 0.0% | 0.0% | 0.0% | 4.0% | 18.4% | 15.9% | **Worse from 2024**; fully replaced the slash name after Aug 2025 |
| `A Pothole` | 0% | 0% | 0% | 5.4% | 5.8% | 4.2% | **New** since Dec 2023 |
| Sub-type with the less common spelling | 0.0% | 0.0% | 0.0% | 0.0% | 1.0% | 3.5% | **Worse from 2025** |
| Canceled with a resolved date (% of canceled) | 8.8% | 10.0% | 11.4% | 69.1% | 100% | 100% | **Changed in 2024**: every canceled report has one since Apr 2024 |
| `last_updated` before opened | 0.0% | 0.0% | 0.0% | 0.2% | 0.6% | 1.0% | **Worse from 2024** |
| `days_to_close` disagrees with the dates | 0.0% | 0.0% | 0.0% | 0.4% | 2.8% | 0.0% | **2024–2025 only** |
| Resolved date has no time (% of resolved) | 100% | 100% | 100% | 100% | 100% | 100% | **Never fixed** |
| Resolved time earlier than opened, same day | 8.0% | 8.7% | 8.3% | 10.8% | 13.5% | 16.4% | Rising, a side effect of the line above as more reports close the same day |
| `additional_questions` broken (% of those filled) | 98.1% | 98.5% | 99.5% | 99.9% | 100% | 100% | **Never fixed** |
| No address | 2.5% | 3.3% | 2.6% | 2.8% | 2.4% | 1.9% | Steady |
| No council district | 2.7% | 3.4% | 2.7% | 3.0% | 3.1% | 5.5% | Steady; higher in 2026 |
| Address with no ZIP | 8.0% | 0% | 0% | 0.0% | 0% | 0% | **Fixed after 2021** |
| `days_to_close` on a still-open report | 0.2% | 0.4% | 0.6% | 1.4% | 2.6% | 14.9% | Expected: recent years have more reports still open |
| No work order | 44.4% | 46.9% | 50.9% | 41.2% | 32.6% | 30.9% | Not an error: more reports get passed to a department system |

### The rare problems (count)

| Problem | 2021* | 2022 | 2023 | 2024 | 2025 | 2026* | Trend |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Address typos / city name missing | 227 | 4 | 1 | 59 | 0 | 2 | Mostly 2021 |
| Address with extra spaces | 66 | 1 | 2 | 1 | 1 | 4 | Mostly 2021 |
| Placeholder `1969-12-31` resolved date | 36 | 0 | 3 | 9 | 4 | 0 | Mostly 2021 |
| Negative `days_to_close` | 68 | 8 | 1 | 2 | 21 | 5 | Mostly 2021 |
| Resolved on an earlier day than opened | 32 | 8 | 1 | 2 | 17 | 5 | Mostly 2021 |
| Coordinates outside Kansas City | 5 | 0 | 1 | 2 | 0 | 0 | Rare |
| Coordinates but no address | 1 | 5 | 10 | 7 | 13 | 11 | Rare |
| Resolved with no resolved date | 0 | 0 | 0 | 0 | 0 | 5 | 2026 only |
| `--` as a sub-type | 0 | 0 | 0 | 2 | 0 | 0 | 2024 only |
| `report_source` = `Web` | 139 | 19 | 76 | 59 | 32 | 13 | Steady, small |
| `report_source` = `App` | 10 | 12 | 15 | 4 | 8 | 17 | Steady, small |

### When things changed

| Change | First seen | Last seen |
| --- | --- | --- |
| `A Pothole` appears | Dec 1, 2023 | still in use |
| `Trash / Recycling / Bulky Services` (slash name) | Mar 1, 2021 | Aug 29, 2025 |
| `Trash  Recycling  Bulky Services` (double spaces) | Nov 10, 2021 (rare until 2024) | still in use |
| Canceled reports with **no** resolved date | Mar 4, 2021 | Apr 27, 2024 |
| `Resolved` (capitalized) | May 18, 2021 (rare until 2024) | still in use |

### Summary

- **Better:** the address problems (missing ZIP, typos, extra spaces) and the 1969 placeholder dates were almost all in 2021, the system's first year.
- **Worse:** the spelling problems (capitalized statuses, renamed categories, "A Pothole", sub-type variants) and canceled reports getting a resolved date all start or jump in **2024**. Something about how reports are recorded changed around late 2023 to 2024.
- **Never fixed:** resolved dates have never had a time, and `additional_questions` has always been broken.
