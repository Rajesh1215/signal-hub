"""Add an item the agent found by hand (an X post, a link the user pasted).

    python3 engine/add_item.py <entity> <url> --title "..." [--snippet "..."]
        [--source "Andrej Karpathy on X"] [--role people] [--person karpathy] [--published 2026-10-17T09:30:00Z]
        [--points 540 --comments 120]   # Reddit/X engagement, shown on the dashboard

The item lands in runs/<today>/collect-local-agent.json as a normal pending
item, so it gets analysed like everything else. Links already collected are
skipped. Uses seen-local.json, never the collector's seen.json.
"""
import sys

from common import ENTITIES, IST, canonical_url, clean_text, item_id, iso, now_utc, parse_time, read_json, write_json


def arg(argv, name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


def main(argv):
    if len(argv) < 2 or "--title" not in argv:
        sys.exit(__doc__)
    entity, url = argv[0], argv[1]
    edir = ENTITIES / entity
    if not (edir / "config.json").exists():
        sys.exit(f"unknown entity '{entity}'")
    iid = item_id(entity, url)
    seen = read_json(edir / "seen-local.json", {})
    if iid in seen or iid in read_json(edir / "seen.json", {}):
        print(f"· already collected: {url}")
        return
    now = now_utc()
    pub = parse_time(arg(argv, "--published"))
    path = edir / "runs" / now.astimezone(IST).strftime("%Y-%m-%d") / "collect-local-agent.json"
    doc = read_json(path, {"entity": entity, "run_at": iso(now), "items": []})
    doc["items"].append({
        "id": iid, "entity": entity, "url": url, "canonical_url": canonical_url(url),
        "title": clean_text(arg(argv, "--title"), 300), "snippet": clean_text(arg(argv, "--snippet", ""), 400),
        "published_at": iso(pub), "found_at": iso(now),
        "source_id": "agent", "source_name": arg(argv, "--source", "Added by agent"),
        "role": arg(argv, "--role", "news"), "type": "agent",
        "competitor_id": None, "person_id": arg(argv, "--person"),
        "meta": {k: int(arg(argv, f"--{k}")) for k in ("points", "comments") if (arg(argv, f"--{k}") or "").isdigit()},
    })
    doc["run_at"] = iso(now)
    write_json(path, doc)
    seen[iid] = iso(now)
    write_json(edir / "seen-local.json", seen)
    print(f"+ added {iid}: {doc['items'][-1]['title'][:80]}")


if __name__ == "__main__":
    main(sys.argv[1:])
