"""Count the normalized requests into the tabs the Sheet shows.

Each tab is a plain list of rows (first row is the header), so the same
tables go to Google Sheets and to CSV without either knowing about the other.
"""

from collections import Counter, defaultdict
from datetime import datetime
from statistics import mean, median

from pipeline.normalize import UNKNOWN_DISTRICT, UNKNOWN_ZIP, Request, status_group

STAT_HEADER = [
    "Reports",
    "Resolved",
    "Open",
    "Referred",
    "Canceled",
    "Median days to resolve",
    "Average days to resolve",
    "Average days open (still open)",
]

SLOW_OPEN_DAYS = 90
OLDEST_OPEN_ROWS = 500
REPEAT_ADDRESS_MIN = 10
WORK_HOURS = range(8, 18)
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
TIME_FMT = "%Y-%m-%d %H:%M"

NOTES = [
    "Canceled requests are not counted as resolved, even though the city records a resolved date for them.",
    "Days to resolve uses resolved requests only. Requests still open are measured separately, by how long they have been waiting.",
    "Referred means passed to another agency; it counts as neither resolved nor open.",
    "Status spellings are merged (e.g. 'resolved' and 'Resolved'), as are duplicate category names.",
    "Requests with no council district are grouped under 'Unknown' rather than dropped.",
    "ZIP codes are read from the address; requests with no address are under 'Unknown'.",
    "Trends by year counts every report since the dataset began in 2021, not only the last 12 months.",
    "Recent months and years look faster to resolve than older ones: their slow requests are still open, so they are not in the average yet.",
    "Repeat addresses include city buildings where staff log reports (City Hall is 414 E 12th St), not only problem spots. The top issue and its share show which is which.",
    "All times are Kansas City local time (America/Chicago).",
]


def _stats(requests: list[Request]) -> list:
    counts = Counter(r.status_group for r in requests)
    days = [r.days_to_resolve for r in requests if r.days_to_resolve is not None]
    ages = [r.open_age_days for r in requests if r.open_age_days is not None]
    return [
        len(requests),
        counts["Resolved"],
        counts["Open"],
        counts["Referred"],
        counts["Canceled"],
        _round(median(days)) if days else "",
        _round(mean(days)) if days else "",
        _round(mean(ages)) if ages else "",
    ]


def _round(value: float) -> float:
    # float() so a median of whole days prints as 3.0, like the averages.
    return round(float(value), 1)


def _pct(part: int, whole: int) -> str:
    return f"{part / whole:.0%}" if whole else ""


def _date(moment: datetime) -> str:
    return f"{moment:%b} {moment.day}, {moment.year}"


def _group(requests: list[Request], key) -> dict[str, list[Request]]:
    groups: dict[str, list[Request]] = defaultdict(list)
    for r in requests:
        groups[key(r)].append(r)
    return groups


def _top_issue(requests: list[Request]) -> tuple[str, int]:
    return Counter(r.issue_type for r in requests).most_common(1)[0]


def _grouped(requests: list[Request], key, label: str, order=None, top_issue=False) -> list[list]:
    groups = _group(requests, key)
    names = order(groups) if order else sorted(groups, key=lambda g: -len(groups[g]))
    header = [label, *STAT_HEADER] + (["Most reported issue"] if top_issue else [])
    rows = [header]
    for name in names:
        extra = [_top_issue(groups[name])[0]] if top_issue else []
        rows.append([name, *_stats(groups[name]), *extra])
    return rows


def _district_order(groups: dict) -> list[str]:
    # Districts in number order, with the unknown bucket last.
    return sorted(groups, key=lambda d: (d == UNKNOWN_DISTRICT, d))


def _busiest_unknown_last(unknown: str):
    return lambda groups: sorted(groups, key=lambda g: (g == unknown, -len(groups[g])))


def _month(r: Request) -> str:
    return r.opened.strftime("%Y-%m")


def _partial_months(window_start: datetime, window_end: datetime) -> set[str]:
    # The window starts mid-month and ends today, so both edge months are
    # short. Labelled, so a half month isn't read as a sudden drop.
    partial = {window_end.strftime("%Y-%m")}
    if window_start.day > 1:
        partial.add(window_start.strftime("%Y-%m"))
    return partial


def _trends(requests: list[Request], window_start: datetime, window_end: datetime) -> list[list]:
    groups = _group(requests, _month)
    partial = _partial_months(window_start, window_end)
    rows = [["Month", *STAT_HEADER, "Note"]]
    for month in sorted(groups):
        rows.append([month, *_stats(groups[month]), "Partial month" if month in partial else ""])
    return rows


def _yearly(counts: list[dict], days: list[dict], today: datetime) -> list[list]:
    """Every year since the dataset began, from the API's own counts (see fetch.yearly_counts)."""
    years: dict[str, Counter] = defaultdict(Counter)
    bounds: dict[str, list[str]] = {}
    for row in counts:
        year, n = row["year"], int(row["reports"])
        years[year]["Reports"] += n
        years[year][status_group(row.get("current_status"))] += n
        first, last = bounds.get(year, [row["first"], row["last"]])
        bounds[year] = [min(first, row["first"]), max(last, row["last"])]
    for row in days:
        if status_group(row.get("current_status")) == "Resolved":
            years[row["year"]]["days"] += float(row["days"])
            years[row["year"]]["resolved_rows"] += int(row["rows"])

    rows = [["Year", "Reports", "Resolved", "Open", "Referred", "Canceled", "Average days to resolve",
             "Change in reports from previous year", "Note"]]
    previous = None
    for year in sorted(years):
        y = years[year]
        first, last = (datetime.fromisoformat(b) for b in bounds[year])
        note = ""
        if first.month != 1:
            note = f"Partial year: data starts {_date(first)}"
        elif int(year) == today.year:
            note = f"Partial year: through {_date(last)}"
        # A change is only meaningful between two full years.
        change = ""
        if previous and not previous[1] and not note:
            change = _pct(y["Reports"] - previous[0], previous[0])
            change = change if change.startswith("-") else "+" + change
        rows.append([
            year, y["Reports"], y["Resolved"], y["Open"], y["Referred"], y["Canceled"],
            _round(y["days"] / y["resolved_rows"]) if y["resolved_rows"] else "", change, note,
        ])
        previous = (y["Reports"], note)
    return rows


def _year_trend(yearly: list[list]) -> str | None:
    full = [row for row in yearly[1:] if not row[-1]]
    if len(full) < 2:
        return None
    (y1, n1), (y2, n2) = (full[0][0], full[0][1]), (full[-1][0], full[-1][1])
    change = _pct(n2 - n1, n1)
    return (f"Reports per year went from {n1:,} in {y1} to {n2:,} in {y2} "
            f"({change if change.startswith('-') else '+' + change}), comparing the first and last full years of data.")


def _oldest_open(requests: list[Request]) -> list[list]:
    still_open = sorted((r for r in requests if r.open_age_days is not None), key=lambda r: -r.open_age_days)
    rows = [["Days open", "Opened", "Category", "Sub-type", "Status", "Department", "District", "ZIP", "Address", "Report ID"]]
    for r in still_open[:OLDEST_OPEN_ROWS]:
        rows.append([
            r.open_age_days, r.opened.strftime(TIME_FMT), r.issue_type, r.issue_sub_type,
            r.status, r.department, r.district, r.zip, r.address, r.id,
        ])
    return rows


def _repeat_addresses(requests: list[Request]) -> list[list]:
    groups = _group([r for r in requests if r.address], lambda r: r.address)
    repeated = sorted((a for a in groups if len(groups[a]) >= REPEAT_ADDRESS_MIN), key=lambda a: -len(groups[a]))
    rows = [["Address", "ZIP", "District", "Reports", "Open", "Most reported issue", "Share of top issue",
             "Different issue types", "First report", "Latest report"]]
    for address in repeated:
        rs = groups[address]
        issue, count = _top_issue(rs)
        rows.append([
            address,
            rs[0].zip,
            Counter(r.district for r in rs).most_common(1)[0][0],
            len(rs),
            sum(1 for r in rs if r.status_group == "Open"),
            issue,
            _pct(count, len(rs)),
            len({r.issue_type for r in rs}),
            min(r.opened for r in rs).strftime(TIME_FMT),
            max(r.opened for r in rs).strftime(TIME_FMT),
        ])
    return rows


def _sources(requests: list[Request]) -> list[list]:
    groups = _group(requests, lambda r: r.source)
    rows = [["How reported", "Reports", "Share", "Median days to resolve"]]
    for source in sorted(groups, key=lambda s: -len(groups[s])):
        days = [r.days_to_resolve for r in groups[source] if r.days_to_resolve is not None]
        rows.append([source, len(groups[source]), _pct(len(groups[source]), len(requests)),
                     _round(median(days)) if days else ""])
    return rows


def _hour_label(hour: int) -> str:
    return f"{hour % 12 or 12} {'AM' if hour < 12 else 'PM'}"


def _timing(requests: list[Request]) -> list[list]:
    days = Counter(r.opened.weekday() for r in requests)
    hours = Counter(r.opened.hour for r in requests)
    n = len(requests)
    rows = [["Day of week", "Reports", "Share"]]
    rows += [[WEEKDAYS[d], days[d], _pct(days[d], n)] for d in range(7)]
    rows += [["", "", ""], ["Hour of day", "Reports", "Share"]]
    rows += [[_hour_label(h), hours[h], _pct(hours[h], n)] for h in range(24)]
    return rows


def _highlights(requests: list[Request], window_start: datetime, window_end: datetime,
                yearly: list[list] | None = None) -> list[list]:
    """The report in sentences, for someone who will not read the tables."""
    n = len(requests)
    if not n:
        return [["Highlights"], ["No reports in this period."]]
    lines = []
    outcomes = Counter(r.status_group for r in requests)
    lines.append(
        f"{n:,} reports from {_date(window_start)} to {_date(window_end)}: "
        f"{_pct(outcomes['Resolved'], n)} resolved, {_pct(outcomes['Open'], n)} still open, "
        f"{_pct(outcomes['Canceled'], n)} canceled."
    )

    days = [r.days_to_resolve for r in requests if r.days_to_resolve is not None]
    if days:
        lines.append(
            f"Half of resolved reports were fixed within {median(days):g} days. The average is "
            f"{mean(days):.1f} days, because a smaller number take much longer."
        )

    by_issue = _group(requests, lambda r: r.issue_type)
    common = sorted(by_issue, key=lambda i: -len(by_issue[i]))
    lines.append(f"The most reported issue is {common[0]} ({len(by_issue[common[0]]):,} reports, "
                 f"{_pct(len(by_issue[common[0]]), n)} of all).")
    typical = {}
    for issue in common[:10]:
        fixed = [r.days_to_resolve for r in by_issue[issue] if r.days_to_resolve is not None]
        if fixed:
            typical[issue] = median(fixed)
    if typical:
        slow = max(typical, key=typical.get)
        lines.append(f"Of the 10 most common issues, {slow} is the slowest to fix: "
                     f"a typical one takes {typical[slow]:g} days.")

    by_zip = _group([r for r in requests if r.zip != UNKNOWN_ZIP], lambda r: r.zip)
    if by_zip:
        z = max(by_zip, key=lambda k: len(by_zip[k]))
        lines.append(f"The busiest area is ZIP {z}, with {len(by_zip[z]):,} reports, "
                     f"most often {_top_issue(by_zip[z])[0]}.")

    by_district = _group([r for r in requests if r.district != UNKNOWN_DISTRICT], lambda r: r.district)
    if by_district:
        ranked = sorted(by_district, key=lambda d: -len(by_district[d]))
        lines.append(f"District {ranked[0]} has the most reports ({len(by_district[ranked[0]]):,}); "
                     f"District {ranked[-1]} has the fewest ({len(by_district[ranked[-1]]):,}).")

    still_open = [r for r in requests if r.open_age_days is not None]
    if still_open:
        slow_open = sum(1 for r in still_open if r.open_age_days > SLOW_OPEN_DAYS)
        oldest = max(still_open, key=lambda r: r.open_age_days)
        lines.append(f"{len(still_open):,} reports are still open, and {slow_open:,} of them "
                     f"({_pct(slow_open, len(still_open))}) have waited more than {SLOW_OPEN_DAYS} days. "
                     f"The oldest opened in this period has been waiting {oldest.open_age_days} days "
                     f"({oldest.issue_type}).")

    trend = _year_trend(yearly) if yearly else None
    if trend:
        lines.append(trend)

    partial = _partial_months(window_start, window_end)
    months = Counter(_month(r) for r in requests if _month(r) not in partial)
    if len(months) >= 2:
        busy, quiet = max(months, key=months.get), min(months, key=months.get)
        label = lambda m: datetime.strptime(m, "%Y-%m").strftime("%B %Y")
        lines.append(f"The busiest month was {label(busy)} ({months[busy]:,} reports); "
                     f"the quietest was {label(quiet)} ({months[quiet]:,}).")

    sources = Counter(r.source for r in requests).most_common(2)
    lines.append(f"The most common way to report is {sources[0][0]} ({_pct(sources[0][1], n)})"
                 + (f", then {sources[1][0]} ({_pct(sources[1][1], n)})." if len(sources) > 1 else "."))

    days_of_week = Counter(r.opened.weekday() for r in requests)
    weekday = mean(days_of_week[d] for d in range(5))
    weekend = mean(days_of_week[d] for d in (5, 6))
    busiest_day = WEEKDAYS[max(range(7), key=lambda d: days_of_week[d])]
    work_hours = sum(1 for r in requests if r.opened.hour in WORK_HOURS)
    lines.append(f"{busiest_day} is the busiest day, and weekends get about {_pct(weekend, weekday)} "
                 f"of a weekday's reports. {_pct(work_hours, n)} arrive between 8 AM and 6 PM.")

    repeat = Counter(r.address for r in requests if r.address)
    repeated = sum(1 for c in repeat.values() if c >= REPEAT_ADDRESS_MIN)
    if repeated:
        lines.append(f"{repeated:,} addresses were reported {REPEAT_ADDRESS_MIN} or more times. Some are "
                     f"city buildings rather than problem spots; see the Repeat addresses tab.")

    dept, dept_count = Counter(r.department for r in requests).most_common(1)[0]
    lines.append(f"The city team handling the most reports is {dept} ({dept_count:,}).")

    return [["Highlights"], *[[line] for line in lines]]


def build(
    requests: list[Request],
    window_start: datetime,
    window_end: datetime,
    generated_at: datetime,
    yearly_counts: tuple[list[dict], list[dict]] | None = None,
) -> dict[str, list[list]]:
    """`yearly_counts` is what fetch.yearly_counts returns; without it, no yearly tab."""
    yearly = _yearly(*yearly_counts, window_end) if yearly_counts else None
    stats = dict(zip(STAT_HEADER, _stats(requests)))
    other = sum(1 for r in requests if r.status_group == "Other")
    unknown_district = sum(1 for r in requests if r.district == UNKNOWN_DISTRICT)
    newest = max((r.opened for r in requests), default=None)

    summary = [
        ["Metric", "Value"],
        ["Report period", f"{window_start:%Y-%m-%d} to {window_end:%Y-%m-%d}"],
        ["Newest report in the city's data", newest.strftime(TIME_FMT) if newest else ""],
        ["Report generated", generated_at.strftime(TIME_FMT)],
        ["", ""],
        *[[name, value] for name, value in stats.items()],
        ["Reports with no council district", unknown_district],
    ]
    if other:
        summary.append(["Reports with an unrecognized status", other])
    summary += [["", ""], ["Notes", ""], *[[note, ""] for note in NOTES]]

    tabs = {
        "Highlights": _highlights(requests, window_start, window_end, yearly),
        "Summary": summary,
        "By category": _grouped(requests, lambda r: r.issue_type, "Category"),
        "By district": _grouped(requests, lambda r: r.district, "District", _district_order, top_issue=True),
        "By area (ZIP)": _grouped(requests, lambda r: r.zip, "ZIP", _busiest_unknown_last(UNKNOWN_ZIP), top_issue=True),
        "By department": _grouped(requests, lambda r: r.department, "Department", top_issue=True),
        "Trends by year": yearly,
        "Trends by month": _trends(requests, window_start, window_end),
        "Oldest open": _oldest_open(requests),
        "Repeat addresses": _repeat_addresses(requests),
        "How people report": _sources(requests),
        "When people report": _timing(requests),
    }
    return {title: rows for title, rows in tabs.items() if rows is not None}
