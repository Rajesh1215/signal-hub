"""List items that still need analysis (for the agent).

    python engine/pending.py                    # all entities, last 7 days
    python engine/pending.py code-quantumn --days 3

Prints a compact list per entity and writes work/pending-<entity>.json
(full records) for the agent to read. Items older than --days are reported
as stale; mark them with save_analysis.py --mark-stale.
"""
import sys
from datetime import timedelta

from common import ROOT, entity_dirs, now_utc, parse_time, read_json, write_json


def load_runs(edir, days=None):
    """Yield (date_dir, items, analysis) for each run date, newest first."""
    runs = edir / "runs"
    if not runs.exists():
        return
    for ddir in sorted(runs.iterdir(), reverse=True):
        if not ddir.is_dir():
            continue
        items = []
        for f in sorted(ddir.glob("collect-*.json")):
            items += read_json(f, {}).get("items", [])
        yield ddir, items, read_json(ddir / "analysis.json", {})


def pending_for(edir, days):
    now = now_utc()
    pending, stale = [], []
    for ddir, items, analysis in load_runs(edir):
        for it in items:
            if it["id"] in analysis:
                continue
            found = parse_time(it.get("found_at"))
            (stale if found and now - found > timedelta(days=days) else pending).append(it)
    return pending, stale


def recent_labelled(edir, days):
    """Non-SKIP items labelled recently, so the agent can spot repeat stories."""
    now, out = now_utc(), []
    for ddir, items, analysis in load_runs(edir):
        for it in items:
            a = analysis.get(it["id"])
            found = parse_time(it.get("found_at"))
            if not a or a.get("label") in ("SKIP", "STALE") or (found and now - found > timedelta(days=days)):
                continue
            out.append(f"  {a['label']:<9} {it['title'][:120]}  [{it['source_name']}]")
    return out


def compact(it):
    m = it.get("meta") or {}
    meta = ", ".join(f"{k}={v}" for k, v in m.items() if k in
                     ("points", "comments", "upvotes", "views", "reactions", "stars_today", "github_stars", "subreddit"))
    who = it.get("competitor_id") or it.get("person_id") or ""
    return (f"{it['id']} | {it['role']}{'/' + who if who else ''} | {it['source_name']} | {it['title'][:140]}"
            + (f" | {it['snippet'][:180]}" if it.get("snippet") else "") + (f" | {meta}" if meta else ""))


def main(argv):
    days = int(argv[argv.index("--days") + 1]) if "--days" in argv else 7
    names = [a for a in argv if not a.startswith("--") and not a.isdigit()]
    total = 0
    for edir in entity_dirs():
        if names and edir.name not in names:
            continue
        cfg = read_json(edir / "config.json")
        pending, stale = pending_for(edir, cfg.get("filters", {}).get("stale_after_days", days))
        total += len(pending)
        write_json(ROOT / "work" / f"pending-{edir.name}.json", pending)
        print(f"\n=== {edir.name}: {len(pending)} pending" + (f", {len(stale)} stale" if stale else ""))
        if pending:
            print(f"labels: {' '.join(cfg['labels'])} | competitor items also: {' '.join(cfg['competitor_labels'])}")
            print(f"timing: {' '.join(cfg['timing'])} | reasons: {' '.join(cfg['reasons'])}")
            print("importance: 1-5 on every non-SKIP item (4-5 = Important) | summary: every non-SKIP item")
            print("flags: " + "; ".join(f"{k}=" + ("/".join(v["values"]) if v["type"] == "enum" else v["type"])
                                        for k, v in cfg["flags"].items()))
        for it in pending:
            print(compact(it))
        ideas = [i for i in read_json(edir / "ideas.json", []) if i.get("status") in ("new", "to_make", "made")][:25]
        if ideas and pending:
            print(f"--- {edir.name}: existing video ideas (update or follow up instead of repeating)")
            for i in ideas:
                print(f"  {i['id']:<42} {i['status']:<8} {i['type']:<9} {i['title'][:90]}")
        recent = recent_labelled(edir, 3)
        if recent and pending:
            print(f"--- {edir.name}: already labelled in the last 3 days (check duplicates against these)")
            for line in recent:
                print(line)
    print(f"\nTOTAL pending: {total}")


if __name__ == "__main__":
    main(sys.argv[1:])
