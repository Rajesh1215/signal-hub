"""Source quality report for the weekly review.

    python engine/report.py            # last 7 days, all entities
    python engine/report.py --days 14

For each source: items collected and how they were labelled. Sources that
only ever produce SKIP are candidates to pause; sources that produce MAKE and
IMPORTANT are the ones to keep.
"""
import sys
from datetime import timedelta

from common import entity_dirs, now_utc, parse_time, read_json
from pending import load_runs

GOOD = ("MAKE", "IMPORTANT", "KNOW-4+", "TEST", "STUDY", "WATCH", "CONTENT", "RELEASE", "FEATURE", "DECISION", "PRACTICE")


def main(argv):
    days = int(argv[argv.index("--days") + 1]) if "--days" in argv else 7
    now = now_utc()
    for edir in entity_dirs():
        cfg = read_json(edir / "config.json")
        rows, totals = {}, {}
        for ddir, items, analysis in load_runs(edir):
            for it in items:
                found = parse_time(it.get("found_at"))
                if found and now - found > timedelta(days=days):
                    continue
                a = analysis.get(it["id"]) or {}
                label = a.get("label", "PENDING")
                if label == "KNOW" and (a.get("importance") or 0) >= 4:
                    label = "KNOW-4+"  # important news counts as useful
                key = it["source_id"] if it["source_id"] != "agent" else it.get("source_name", "agent")  # Reddit/X by page
                r = rows.setdefault(key, {})
                r[label] = r.get(label, 0) + 1
                totals[label] = totals.get(label, 0) + 1
        print(f"\n{cfg['name']}: last {days} days  " + ", ".join(f"{k} {v}" for k, v in sorted(totals.items())))
        ranked = sorted(rows.items(), key=lambda kv: -sum(kv[1].get(l, 0) for l in GOOD))
        for sid, r in ranked:
            n, good = sum(r.values()), sum(r.get(l, 0) for l in GOOD)
            note = "  <- only SKIP: consider pausing" if n >= 8 and r.get("SKIP", 0) == n else ""
            print(f"  {sid:<28} {n:>4} items  {good:>3} useful  " +
                  " ".join(f"{k}:{v}" for k, v in sorted(r.items())) + note)


if __name__ == "__main__":
    main(sys.argv[1:])
