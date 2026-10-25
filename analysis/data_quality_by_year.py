"""Count each data problem per year opened. Changes nothing. Prints JSON."""
import glob
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime

raw = sys.argv[1] if len(sys.argv) > 1 else "data/raw"
OPEN = ("new", "received", "assigned", "active", "referred")
total = Counter()                     # reports per year
denom = defaultdict(Counter)          # per-problem denominators per year
flags = defaultdict(Counter)          # problem -> year -> count
vals = defaultdict(Counter)           # (field, value) -> year counts, for spelling variants


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


for f in sorted(glob.glob(f"{raw}/*/*.json")):
    for r in json.load(open(f)):
        y = r["open_date_time"][:4]
        total[y] += 1
        flag = lambda k: flags[k].update([y])
        for k in ("current_status", "issue_type", "issue_sub_type", "report_source"):
            vals[(k, r.get(k))][y] += 1

        status = (r.get("current_status") or "").lower()
        raw_status = r.get("current_status") or ""
        opened = datetime.fromisoformat(r["open_date_time"])
        resolved = datetime.fromisoformat(r["resolved_date"]) if r.get("resolved_date") else None
        updated = datetime.fromisoformat(r["last_updated"]) if r.get("last_updated") else None
        d = r.get("days_to_close")

        if raw_status and raw_status != raw_status.lower():
            flag("status_capitalized")
        it = r.get("issue_type") or ""
        if "  " in it:
            flag("issue_type_double_space")
        if re.match(r"^(A|An|The) ", it):
            flag("issue_type_article")
        if (r.get("issue_sub_type") or "") == "--":
            flag("sub_type_dashes")

        if resolved:
            denom["resolved_midnight"][y] += 1
            if resolved.time() == datetime.min.time():
                flag("resolved_midnight")
            if resolved.year < 2000:
                flag("resolved_placeholder_1969")
            elif resolved < opened and resolved.date() == opened.date():
                flag("resolved_same_day_earlier")
            elif resolved < opened:
                flag("resolved_earlier_day")
        if updated and updated < opened:
            flag("updated_before_opened")

        if d not in (None, ""):
            dv = float(d)
            if dv < 0:
                flag("days_negative")
            if status in OPEN:
                flag("days_on_open")
            if resolved and resolved >= opened and abs((resolved - opened).days - dv) > 1:
                flag("days_disagree")

        if status == "canceled":
            denom["canceled_with_resolved"][y] += 1
            if resolved:
                flag("canceled_with_resolved")
        if status in ("resolved", "closed") and not resolved:
            flag("resolved_no_date")

        addr = r.get("incident_address") or ""
        lat, lon = r.get("latitude"), r.get("longitude")
        if not addr:
            flag("no_address")
        else:
            if not re.search(r"\b6\d{4}\b", addr):
                flag("address_no_zip")
            if "kansas city" not in addr.lower():
                flag("address_not_kc")
            if "  " in addr or addr != addr.strip():
                flag("address_spaces")
        if lat and lon:
            la, lo = float(lat), float(lon)
            if not (38.7 < la < 39.5 and -95.0 < lo < -94.2):
                flag("coords_outside_kc")
            if not addr:
                flag("coords_no_address")
        if not r.get("council_district"):
            flag("no_district")

        aq = r.get("additional_questions")
        if aq:
            denom["questions_invalid"][y] += 1
            try:
                json.loads(aq)
            except ValueError:
                flag("questions_invalid")
        if not r.get("workorder_"):
            flag("no_workorder")

# Spelling variants: within each group of values that differ only in case or
# punctuation, everything but the most common spelling is a variant.
for field, key in (("issue_sub_type", "sub_type_variant"),):
    groups = defaultdict(list)
    for (k, v), years in vals.items():
        if k == field and v:
            groups[norm(v)].append((sum(years.values()), v, years))
    for g in groups.values():
        if len(g) > 1:
            for _, v, years in sorted(g, reverse=True)[1:]:
                for y, c in years.items():
                    flags[key][y] += c

for name, value in (("source_web", "Web"), ("source_app", "App"), ("source_web_rai", "WEB RAI")):
    flags[name] = vals[("report_source", value)]
for name, value in (("trash_slash", "Trash / Recycling / Bulky Services"),
                    ("trash_double_space", "Trash  Recycling  Bulky Services")):
    flags[name] = vals[("issue_type", value)]

print(json.dumps({"total": total, "denom": denom, "flags": flags}))
