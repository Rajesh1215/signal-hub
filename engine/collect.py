"""Collect new items from every active source of every entity.

    python engine/collect.py                 # all entities (GitHub Actions: "auto" sources)
    python engine/collect.py --local         # "local" sources (Reddit) from your Mac, during analyze today
    python engine/collect.py code-quantumn   # one entity
    python engine/collect.py --test <entity> # fetch and report, write nothing
    python engine/collect.py <entity> --only id1,id2   # test single sources (writes nothing)

Writes entities/<e>/runs/<YYYY-MM-DD>/collect-<HHMM>.json (IST) with only NEW items,
and updates seen.json (dedupe across days) and health.json (per-source stats).
"""
import sys
import traceback
from datetime import timedelta

from adapters import run_adapter
from common import (IST, canonical_url, resolve_gnews, entity_dirs, flatten_sources, item_id, iso,
                    now_utc, parse_time, read_json, write_json)

SEEN_DAYS = 90
HISTORY_DAYS = 30


def collect_entity(edir, test=False, only=None, mode="auto"):
    """mode "auto" runs in GitHub Actions and owns seen.json/health.json.
    mode "local" runs on the user's Mac (sites that block cloud servers) and owns
    seen-local.json/health-local.json, so the two never edit the same file."""
    entity = edir.name
    sfx = "" if mode == "auto" else "-local"
    cfg = read_json(edir / "config.json")
    sources = read_json(edir / "sources.json", {"sources": []})
    seen = read_json(edir / f"seen{sfx}.json", {})
    other_seen = read_json(edir / ("seen-local.json" if mode == "auto" else "seen.json"), {})
    health = read_json(edir / f"health{sfx}.json", {})
    now = now_utc()
    default_age = cfg.get("filters", {}).get("max_age_days", 3)
    default_max_new = cfg.get("filters", {}).get("max_new_per_source", 20)
    new_items, report = [], []

    for src in flatten_sources(sources):
        if only and src["id"] not in only:
            continue
        if (src.get("mode", "auto") != mode and not (only and src.get("mode") == "local")) \
                or src.get("status", "active") not in ("active", "trial", *(["paused", "candidate"] if only else [])):
            continue
        sid = src["id"]
        h = health.setdefault(sid, {"consecutive_errors": 0, "history": []})
        try:
            items, state = run_adapter(src, h.get("state", {}))
            h["state"] = {k: v for k, v in (state or {}).items() if v}
            h["consecutive_errors"], h["last_ok"] = 0, iso(now)
            h.pop("last_error", None)
        except Exception as e:  # noqa: BLE001 — one broken source must not stop the run
            err_msg = str(e)
            if "rate-limited us earlier in this run" in err_msg:
                h["last_error"] = f"{type(e).__name__}: {err_msg[:160]}"
                report.append(f"  ~ {sid}: {h['last_error']}")
            else:
                h["consecutive_errors"] = h.get("consecutive_errors", 0) + 1
                h["last_error"] = f"{type(e).__name__}: {err_msg[:160]}"
                report.append(f"  ✗ {sid}: {h['last_error']}")
            if test and not isinstance(e, (OSError, ValueError)):
                traceback.print_exc()
            continue

        baseline = (src.get("adapter", src.get("type")) in ("page", "sitemap") or src.get("baseline")) and not h.get("baselined")
        max_age = timedelta(days=src.get("max_age_days", default_age))
        max_new = src.get("max_new", default_max_new)
        found = fresh = 0
        for it in items:
            if not it.get("url"):
                continue
            found += 1
            if not baseline and fresh >= max_new:  # busy feeds: keep the newest few per run
                continue
            iid = item_id(entity, it["url"])
            if iid in other_seen:
                continue
            if iid in seen:
                # still listed by the source: refresh now and then so pruning only
                # forgets items that disappeared (pages and sitemaps never re-flood)
                if now - (parse_time(seen[iid]) or now) > timedelta(days=30):
                    seen[iid] = iso(now)
                continue
            pub = parse_time(it.get("published_at"))
            if pub and now - pub > max_age:
                continue
            seen[iid] = iso(now)
            if baseline:  # first look at a page: remember what exists, report nothing
                continue
            fresh += 1
            if "news.google.com/" in it["url"]:  # keep the id from Google's link, show the publisher's
                it["url"] = resolve_gnews(it["url"])
            new_items.append({
                "id": iid, "entity": entity, "url": it["url"], "canonical_url": canonical_url(it["url"]),
                "title": it.get("title", ""), "snippet": it.get("snippet", "")[:900],
                "published_at": it.get("published_at"), "found_at": iso(now),
                "source_id": sid, "source_name": src.get("name", sid), "role": src.get("role", "news"),
                "type": src.get("type"), "competitor_id": src.get("competitor_id"),
                "person_id": src.get("person_id"), "meta": it.get("meta", {}),
            })
        if baseline:
            h["baselined"] = True
        h["last_run"] = iso(now)
        h["history"] = ([x for x in h["history"]
                         if parse_time(x["at"]) and now - parse_time(x["at"]) < timedelta(days=HISTORY_DAYS)]
                        + [{"at": iso(now), "found": found, "new": fresh}])
        report.append(f"  {'·' if fresh == 0 else '+'} {sid}: {found} found, {fresh} new"
                      + (" (baseline)" if baseline else ""))

    # forget very old IDs so seen.json stays small
    cutoff = now - timedelta(days=SEEN_DAYS)
    seen = {k: v for k, v in seen.items() if parse_time(v) and parse_time(v) > cutoff}

    print(f"[{entity}] {len(new_items)} new items")
    print("\n".join(report))
    if test:
        for it in new_items[:15]:
            print(f"    - [{it['source_id']}] {it['title'][:90]}")
        return new_items

    local = now.astimezone(IST)
    if new_items:
        write_json(edir / "runs" / local.strftime("%Y-%m-%d") / f"collect{sfx}-{local.strftime('%H%M')}.json",
                   {"entity": entity, "run_at": iso(now), "items": new_items})
    write_json(edir / f"seen{sfx}.json", seen)
    write_json(edir / f"health{sfx}.json", health)
    return new_items


def main(argv):
    test = "--test" in argv
    only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else None
    if only:
        test = True  # testing single sources never writes anything
    skip = {argv[argv.index("--only") + 1]} if only else set()
    names = [a for a in argv if not a.startswith("--") and a not in skip]
    dirs = [d for d in entity_dirs() if not names or d.name in names]
    mode = "local" if "--local" in argv else "auto"
    total = sum(len(collect_entity(d, test=test, only=only, mode=mode)) for d in dirs)
    print(f"done: {total} new items across {len(dirs)} entities")


if __name__ == "__main__":
    main(sys.argv[1:])
