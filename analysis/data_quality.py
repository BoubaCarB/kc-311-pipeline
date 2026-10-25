"""Scan every raw file and report inconsistencies, field by field. Changes nothing."""
import glob
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime

raw = sys.argv[1] if len(sys.argv) > 1 else "data/raw"
FIELDS = ["reported_issue", "workorder_", "current_status", "open_date_time", "resolved_date",
          "days_to_close", "report_source", "issue_type", "issue_sub_type", "department_work_group",
          "incident_address", "latitude", "longitude", "lat_long", "additional_questions",
          "last_updated", "council_district", "source_category"]

n = 0
missing = Counter()
values = defaultdict(Counter)       # small-vocabulary fields
ids = Counter()
ex = defaultdict(list)              # examples per finding
count = Counter()

def note(key, example):
    count[key] += 1
    if len(ex[key]) < 3:
        ex[key].append(example)

def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())

for f in sorted(glob.glob(f"{raw}/*/*.json")):
    for r in json.load(open(f)):
        n += 1
        rid = r.get("reported_issue")
        ids[rid] += 1
        for k in FIELDS:
            if r.get(k) in (None, ""):
                missing[k] += 1
        extra = set(r) - set(FIELDS)
        for k in extra:
            note(f"unexpected field {k}", rid)
        for k in ("current_status", "report_source", "issue_type", "issue_sub_type",
                  "department_work_group", "council_district", "source_category"):
            values[k][r.get(k)] += 1

        status = (r.get("current_status") or "").lower()
        opened = datetime.fromisoformat(r["open_date_time"]) if r.get("open_date_time") else None
        resolved = datetime.fromisoformat(r["resolved_date"]) if r.get("resolved_date") else None
        updated = datetime.fromisoformat(r["last_updated"]) if r.get("last_updated") else None
        d = r.get("days_to_close")

        if opened and opened.tzinfo is None and n == 1:
            note("timestamps have no timezone", r["open_date_time"])
        if resolved and status not in ("resolved", "closed"):
            note(f"resolved_date set but status is '{status}'", rid)
        if not resolved and status in ("resolved", "closed"):
            note("status resolved but no resolved_date", rid)
        if resolved and opened and resolved < opened:
            note("resolved before opened", f"{rid}: opened {r['open_date_time']}, resolved {r['resolved_date']}")
        if resolved and resolved.time() == datetime.min.time():
            note("resolved_date at exactly midnight (date only, no real time)", f"{rid}: {r['resolved_date']}")
        if updated and opened and updated < opened:
            note("last_updated before opened", f"{rid}: opened {r['open_date_time']}, updated {r['last_updated']}")
        if d not in (None, ""):
            dv = float(d)
            if dv < 0:
                note("negative days_to_close", f"{rid}: {d} ({status})")
            if dv != int(dv):
                note("days_to_close not a whole number", f"{rid}: {d}")
            if status in ("new", "received", "assigned", "active", "referred"):
                note("days_to_close on a still-open report (it's the age, not time to fix)", f"{rid}: {d} days, {status}")
            if resolved and opened and resolved >= opened:
                real = (resolved - opened).days
                if abs(real - dv) > 1:
                    note("days_to_close disagrees with the two dates by more than a day",
                         f"{rid}: field {d}, dates say {real}")

        lat, lon = r.get("latitude"), r.get("longitude")
        if lat and lon:
            la, lo = float(lat), float(lon)
            if not (38.7 < la < 39.5 and -95.0 < lo < -94.2):
                note("coordinates outside the Kansas City area", f"{rid}: {lat}, {lon} ({r.get('incident_address')})")
            ll = r.get("lat_long")
            if ll and ll.get("coordinates") and (abs(ll["coordinates"][1] - la) > 1e-6 or abs(ll["coordinates"][0] - lo) > 1e-6):
                note("lat_long disagrees with latitude/longitude", rid)
        elif r.get("incident_address"):
            note("address but no coordinates", f"{rid}: {r['incident_address']}")
        if (lat or lon) and not r.get("incident_address"):
            note("coordinates but no address", f"{rid}: {lat}, {lon}")

        addr = r.get("incident_address") or ""
        if addr:
            if not re.search(r"\b6\d{4}\b", addr):
                note("address with no ZIP code", f"{rid}: {addr}")
            if "kansas city" not in addr.lower():
                note("address not in 'Kansas City'", f"{rid}: {addr}")
            if "  " in addr or addr != addr.strip():
                note("address with extra spaces", f"{rid}: {addr!r}")

        aq = r.get("additional_questions")
        if aq:
            try:
                json.loads(aq)
            except ValueError:
                note("additional_questions is not valid JSON", f"{rid}: {aq[:90]}")

        for k in ("issue_type", "issue_sub_type", "department_work_group"):
            v = r.get(k) or ""
            if "  " in v or v != v.strip():
                note(f"{k} with double or stray spaces", repr(v))
            if re.match(r"^(A|An|The) ", v):
                note(f"{k} starting with an article", v)

dupes = {k: v for k, v in ids.items() if v > 1}

print(f"ROWS: {n:,}\n")
print("MISSING VALUES PER FIELD")
for k in FIELDS:
    if missing[k]:
        print(f"  {k}: {missing[k]:,} ({missing[k]/n:.1%})")
print(f"\nDUPLICATE reported_issue IDs: {len(dupes):,}", list(dupes.items())[:3])
print("\nFINDINGS")
for k, c in count.most_common():
    print(f"  [{c:,}] {k}")
    for e in ex[k]:
        print(f"       e.g. {e}")

print("\nSAME VALUE, DIFFERENT SPELLING (grouped by letters/numbers only, case ignored)")
for k in ("current_status", "report_source", "issue_type", "issue_sub_type", "department_work_group", "source_category"):
    groups = defaultdict(list)
    for v, c in values[k].items():
        groups[norm(v or "")].append((v, c))
    for g in groups.values():
        if len(g) > 1:
            print(f"  {k}: " + " | ".join(f"{v!r} ({c:,})" for v, c in sorted(g, key=lambda x: -x[1])))

print("\nVOCABULARY SIZES")
for k, c in values.items():
    print(f"  {k}: {len(c)} distinct")
print("  current_status:", dict(values["current_status"].most_common()))
print("  council_district:", dict(values["council_district"].most_common()))
print("  report_source:", dict(values["report_source"].most_common()))
print("  source_category:", dict(values["source_category"].most_common()))
