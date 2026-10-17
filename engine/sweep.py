"""List the pages the agent reads by hand during "analyze today" (Reddit, X).

    python3 engine/sweep.py                 # all niches
    python3 engine/sweep.py code-quantumn

These sites block scripts, so the agent opens each page in its browser like a
normal reader, picks the meaningful posts and adds them with add_item.py.
"""
import sys

from common import entity_dirs, flatten_sources, read_json

LIMITS = {"reddit_manual": "up to 3 top posts from the last 24 h", "x_manual": "up to 2 posts from the last 24 h"}


def main(argv):
    for edir in entity_dirs():
        if argv and edir.name not in argv:
            continue
        rows = [s for s in flatten_sources(read_json(edir / "sources.json", {}))
                if s.get("sweep") and s.get("status", "active") == "active"]
        if not rows:
            continue
        print(f"\n=== {edir.name}: {len(rows)} pages to check")
        for s in rows:
            extra = f" --role people --person {s['person_id']}" if s.get("person_id") else ""
            print(f"{s['name']:<34} {s['url']}  ({LIMITS.get(s['type'], 'meaningful posts only')}){extra}")


if __name__ == "__main__":
    main(sys.argv[1:])
