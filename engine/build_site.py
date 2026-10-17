"""Build the GitHub Pages dashboard data from run + analysis files.

    python engine/build_site.py

Writes docs/data/<entity>.json (items from the last 60 days with their labels),
docs/data/meta.json (entities, label/flag definitions, manual sources,
competitors, source health) and copies site/index.html to docs/index.html.
"""
import re
import shutil
from datetime import timedelta

from common import read_health, DOCS, ROOT, entity_dirs, flatten_sources, iso, now_utc, parse_time, read_json, write_json
from pending import load_runs

KEEP_DAYS = 60
META_KEYS = ("points", "comments", "upvotes", "views", "reactions", "stars_today",
             "github", "github_stars", "discussion", "subreddit", "author", "image", "anniversary_date", "years")
JUNK_IMAGE = re.compile(r"/emoji/|avatars\.githubusercontent|gravatar\.com|feedburner|pixel|spacer|1x1", re.I)


def thumbnail(url, meta):
    """Feed image if there is a good one, else a known preview for the link type."""
    img = meta.get("image")
    if img and not JUNK_IMAGE.search(img):
        return img
    m = re.search(r"youtube\.com/(?:watch\?v=|shorts/)([\w-]{6,})", url)
    if m:
        return f"https://i.ytimg.com/vi/{m.group(1)}/mqdefault.jpg"
    m = re.match(r"https://github\.com/([\w.-]+)/([\w.-]+)(?:/releases/tag/[^/]+)?/?$", url)
    if m and m.group(1) not in ("orgs", "topics", "features", "trending", "sponsors"):
        return f"https://opengraph.githubassets.com/1/{m.group(1)}/{m.group(2)}"
    m = re.match(r"https://huggingface\.co/papers/([\w.]+)$", url)
    if m:
        return f"https://cdn-thumbnails.huggingface.co/social-thumbnails/papers/{m.group(1)}.png"
    return None


def build_entity(edir):
    now = now_utc()
    cfg = read_json(edir / "config.json")
    out = []
    for ddir, items, analysis in load_runs(edir):
        for it in items:
            found = parse_time(it.get("found_at"))
            if found and now - found > timedelta(days=KEEP_DAYS):
                continue
            a = analysis.get(it["id"], {})
            meta = {k: v for k, v in (it.get("meta") or {}).items() if k in META_KEYS and v}
            img = thumbnail(it["url"], meta)
            meta.pop("image", None)
            out.append({
                "id": it["id"], "title": it["title"], "url": it["url"], "source": it["source_name"],
                "role": it.get("role", "news"), "competitor_id": it.get("competitor_id"),
                "person_id": it.get("person_id"), "found_at": it.get("found_at"),
                "published_at": it.get("published_at"),
                "meta": meta, "image": img, "snippet": (it.get("snippet") or "")[:220],
                "status": "analyzed" if a and a.get("label") != "STALE" else ("stale" if a else "pending"),
                **{k: a[k] for k in ("label", "importance", "timing", "evergreen", "reason", "flags", "summary") if k in a},
            })
    for x in out:  # "when" = publish time, unless missing or in the future (bad feed dates)
        pub = x.get("published_at")
        x["when"] = pub if pub and pub <= (x.get("found_at") or pub) else x.get("found_at")
    out.sort(key=lambda x: x.get("when") or "", reverse=True)
    write_json(DOCS / "data" / f"{edir.name}.json", out)

    sources = read_json(edir / "sources.json", {"sources": []})
    health = read_health(edir)
    src_rows, manual = [], []
    for s in flatten_sources(sources):
        if s.get("mode") == "manual":
            manual.append({"name": s.get("name", s["id"]), "url": s.get("url"), "type": s.get("type"),
                           "role": s.get("role", "news"), "why": s.get("why", ""), "tags": s.get("tags", []),
                           "sweep": bool(s.get("sweep")), "members": s.get("members", [])})
            continue
        h = health.get(s["id"], {})
        week = [x for x in h.get("history", [])
                if parse_time(x["at"]) and now - parse_time(x["at"]) < timedelta(days=7)]
        src_rows.append({"id": s["id"], "name": s.get("name", s["id"]), "role": s.get("role", "news"),
                         "type": s.get("type"), "status": s.get("status", "active"), "why": s.get("why", ""),
                         "last_ok": h.get("last_ok"), "errors": h.get("consecutive_errors", 0),
                         "last_error": h.get("last_error"), "new_7d": sum(x["new"] for x in week),
                         "broken": h.get("consecutive_errors", 0) >= 3})
    last_collect = max((h.get("last_run") or "" for h in health.values()), default="") or None
    last_analysis = max((a.get("analyzed_at") or "" for _, _, an in load_runs(edir) for a in an.values()),
                        default="") or None
    return {"id": edir.name, "name": cfg["name"], "color": cfg.get("color", "#22D3EE"), "niche": cfg.get("niche", ""),
            "order": cfg.get("order", 99), "last_collect": last_collect, "last_analysis": last_analysis,
            "labels": cfg["labels"], "competitor_labels": cfg.get("competitor_labels", []),
            "flags": cfg["flags"], "count": len(out),
            "pending": sum(1 for x in out if x["status"] == "pending"),
            "competitors": [{"id": c["id"], "name": c["name"]} for c in sources.get("competitors", [])],
            "manual": manual, "sources": src_rows}


def main():
    entities = sorted((build_entity(d) for d in entity_dirs()), key=lambda e: (e["order"], e["name"]))
    write_json(DOCS / "data" / "meta.json", {"generated_at": iso(now_utc()), "entities": entities})
    shutil.copy(ROOT / "site" / "index.html", DOCS / "index.html")
    (DOCS / ".nojekyll").write_text("")
    print(f"built dashboard for {len(entities)} entities")


if __name__ == "__main__":
    main()
