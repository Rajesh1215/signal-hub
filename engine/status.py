"""One-screen status for the agent: last collection, pending work, broken sources.

    python engine/status.py
"""
from datetime import timedelta

from common import read_health, IST, entity_dirs, flatten_sources, now_utc, parse_time, read_json
from pending import load_runs, pending_for


def main():
    now = now_utc()
    for edir in entity_dirs():
        cfg = read_json(edir / "config.json")
        health = read_health(edir)
        stale_days = cfg.get("filters", {}).get("stale_after_days", 7)
        pending, stale = pending_for(edir, stale_days)
        last_runs = [parse_time(h.get("last_run")) for h in health.values() if h.get("last_run")]
        last = max(last_runs).astimezone(IST).strftime("%d %b %H:%M IST") if last_runs else "never"
        labels = {}
        for ddir, items, analysis in load_runs(edir):
            if ddir.name != now.astimezone(IST).strftime("%Y-%m-%d"):
                continue
            for a in analysis.values():
                labels[a.get("label")] = labels.get(a.get("label"), 0) + 1
        print(f"\n{cfg['name']} ({edir.name})  last collect: {last}")
        print(f"  pending: {len(pending)}   stale (>{stale_days}d, unanalysed): {len(stale)}")
        if labels:
            print("  labelled today: " + ", ".join(f"{k} {v}" for k, v in sorted(labels.items())))
        for s in flatten_sources(read_json(edir / "sources.json", {})):
            if s.get("mode") == "manual" or s.get("status", "active") not in ("active", "trial"):
                continue
            h = health.get(s["id"], {})
            if h.get("consecutive_errors", 0) >= 3:
                print(f"  BROKEN  {s['id']}: {h.get('consecutive_errors')} errors in a row, last: {h.get('last_error')}")
            elif h.get("history") and len(h["history"]) >= 10 and not any(
                    x["new"] for x in h["history"] if parse_time(x["at"]) and now - parse_time(x["at"]) < timedelta(days=14)):
                print(f"  QUIET   {s['id']}: nothing new in 14 days")


if __name__ == "__main__":
    main()
