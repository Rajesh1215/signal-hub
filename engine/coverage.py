"""Did we catch this story? Searches everything collected in the last N days.

    python3 engine/coverage.py "Gemini 4 Argon"                 # words from the headline
    python3 engine/coverage.py https://blog.google/...          # or a link
    python3 engine/coverage.py "repo rate" --entity capital-kinetics --days 14

Prints each match with its niche, label, source and when it was found. Used by
the weekly review's missed-news check: no match = a gap to trace back to its
original source.
"""
import sys
from datetime import timedelta

from common import IST, canonical_url, entity_dirs, now_utc, parse_time
from pending import load_runs

STOP = {"the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "is", "its", "it", "new", "how", "why", "what"}


def main(argv):
    if not argv:
        sys.exit(__doc__)
    query = argv[0]
    days = int(argv[argv.index("--days") + 1]) if "--days" in argv else 7
    only = argv[argv.index("--entity") + 1] if "--entity" in argv else None
    now = now_utc()
    is_url = query.startswith("http")
    target = canonical_url(query) if is_url else None
    words = [w for w in query.lower().split() if w not in STOP]
    hits = []
    for edir in entity_dirs():
        if only and edir.name != only:
            continue
        for ddir, items, analysis in load_runs(edir):
            for it in items:
                found = parse_time(it.get("found_at"))
                if found and now - found > timedelta(days=days):
                    continue
                if is_url:
                    ok = it.get("canonical_url") == target or target in (it.get("url") or "")
                else:
                    hay = f"{it.get('title', '')} {it.get('snippet', '')}".lower()
                    ok = words and sum(w in hay for w in words) >= max(1, round(len(words) * 0.7))
                if ok:
                    a = analysis.get(it["id"], {})
                    hits.append((found, edir.name, a.get("label", "PENDING"), a.get("importance"), it))
    if not hits:
        print(f"✗ not caught in the last {days} days: {query}")
        sys.exit(1)
    hits.sort(key=lambda h: h[0] or now)
    print(f"✓ caught {len(hits)} time(s); first:")
    for found, ent, label, imp, it in hits[:10]:
        when = found.astimezone(IST).strftime("%d %b %H:%M") if found else "?"
        print(f"  {when}  {ent:<17} {label:<9}{f' imp {imp}' if imp else '':<7} {it['source_name']:<28} {it['title'][:80]}")


if __name__ == "__main__":
    main(sys.argv[1:])
