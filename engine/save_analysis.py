"""Validate the agent's payloads and save them next to the items they describe.

    python engine/save_analysis.py <entity> <payloads.json>
    python engine/save_analysis.py <entity> --mark-stale [--days 7]

Rules enforced: label from config (competitor items may also use competitor
labels); MAKE needs timing + evergreen 1-5; every non-SKIP item needs a summary;
non-SKIP news items need importance 1-5 and flags.category; flags typed.

payloads.json is a list of objects:
  {"id": "...", "label": "MAKE", "importance": 4, "timing": "NOW", "evergreen": 2,
   "reason": "model_release", "flags": {"category": "model"}, "summary": "... Hook: '...'"}

Every field is checked against entities/<entity>/config.json. Invalid payloads
are rejected with a message (fix and re-run); valid ones are merged into
runs/<date>/analysis.json. Exit code 1 if anything was rejected.
"""
import json
import re
import sys
from collections import defaultdict
from datetime import date

from common import ENTITIES, iso, now_utc, read_json, write_json
from pending import load_runs, pending_for

_DUP_STOP = {
    "the", "and", "for", "with", "that", "this", "from", "are", "was", "have", "has", "not", "but",
    "what", "when", "why", "how", "who", "will", "can", "now", "new", "more", "about", "into",
    "over", "after", "than", "just", "first", "their", "they", "them", "been", "could", "would",
    "should", "other", "says", "said", "report", "reports", "news", "blog", "updates", "update",
    "today", "2026", "2027", "ai", "models", "model", "using", "based", "data", "make", "best",
    "top", "most", "some", "your", "here", "introducing", "launches", "launch", "announces",
    "announce", "releases", "release", "daily", "users", "user", "million", "billion", "weekly",
    "recap", "trending", "changelog", "available", "features", "feature", "plans", "plan",
    "wins", "gets", "hits", "tops", "gains", "speed", "push", "free", "paid", "next", "week",
    "month", "year", "years", "time", "company", "companies", "tech", "india", "indian", "global",
    "openai", "anthropic", "claude", "google", "meta", "deepseek", "qwen", "nvidia", "microsoft",
    "amazon", "aws", "apple", "github", "hugging", "face", "vercel", "mint", "market", "markets",
    "stock", "stocks", "shares", "price", "prices", "people", "searching", "on", "in", "of", "to",
    "agent", "agents", "platform", "app", "apps", "system", "systems"
}


def _sig_tokens(title):
    t = re.sub(r"['’]s\b", "", (title or "").lower())
    return {w for w in re.findall(r"[a-z0-9][a-z0-9.\-+]*", t)
            if (len(w) >= 4 or any(c.isdigit() for c in w)) and w not in _DUP_STOP}


def _sig_bigrams(title):
    t = re.sub(r"['’]s\b", "", (title or "").lower())
    words = [w for w in re.findall(r"[a-z0-9][a-z0-9.\-+]*", t) if len(w) >= 2 and w not in _DUP_STOP]
    return {f"{words[i]} {words[i+1]}" for i in range(len(words) - 1)
            if len(words[i]) >= 4 or len(words[i+1]) >= 4 or any(c.isdigit() for c in words[i] + words[i+1])}


def _find_orphaned_duplicates(payloads, roles, titles, recent_runs):
    """Reject SKIP(duplicate) clusters when 2+ items share a story and 0 non-competitor items cover it."""
    payload_ids = {p.get("id") for p in payloads}
    kept_token_sets = []
    for _, items, ana in recent_runs:
        for it in items:
            iid = it["id"]
            if iid not in payload_ids and it.get("role", "news") != "competitor":
                if ana.get(iid, {}).get("label") not in (None, "SKIP", "STALE"):
                    kept_token_sets.append(_sig_tokens(it.get("title", "")))
    for p in payloads:
        iid = p.get("id")
        if iid in titles and roles.get(iid) != "competitor" and p.get("label") not in (None, "SKIP", "STALE"):
            kept_token_sets.append(_sig_tokens(titles.get(iid, "")))

    orphaned = defaultdict(list)
    for p in payloads:
        iid = p.get("id")
        if roles.get(iid) != "competitor" and p.get("label") == "SKIP" and p.get("reason") == "duplicate":
            t = titles.get(iid, "")
            itoks = _sig_tokens(t)
            if not any(len(itoks & ktoks) >= 2 for ktoks in kept_token_sets):
                for bg in _sig_bigrams(t):
                    orphaned[bg].append(iid)

    bad = {}
    for bg, iids in orphaned.items():
        if len(iids) >= 2:
            for iid in iids:
                bad.setdefault(iid, bg)
    return bad


def _is_date(v):
    try:
        return isinstance(v, str) and len(v) == 10 and bool(date.fromisoformat(v))
    except ValueError:
        return False


def validate(p, cfg, role):
    errs = []
    labels = cfg["labels"] + (cfg.get("competitor_labels", []) if role == "competitor" else [])
    if p.get("label") not in labels + ["STALE"]:
        errs.append(f"label '{p.get('label')}' not in {labels}")
    if p.get("label") == "MAKE":
        if p.get("timing") not in cfg["timing"]:
            errs.append(f"MAKE needs timing in {cfg['timing']}")
        if not isinstance(p.get("evergreen"), int) or not 1 <= p["evergreen"] <= 5:
            errs.append("MAKE needs evergreen 1-5")
    if p.get("reason") and p["reason"] not in cfg["reasons"]:
        errs.append(f"reason '{p['reason']}' not in config reasons")
    for k, v in (p.get("flags") or {}).items():
        spec = cfg["flags"].get(k)
        if spec is None:
            errs.append(f"unknown flag '{k}'")
        elif spec["type"] == "bool" and not isinstance(v, bool):
            errs.append(f"flag '{k}' must be true/false")
        elif spec["type"] == "enum" and v not in spec["values"]:
            errs.append(f"flag '{k}' must be one of {spec['values']}")
        elif spec["type"] == "int" and not isinstance(v, int):
            errs.append(f"flag '{k}' must be an integer")
        elif spec["type"] == "date" and not _is_date(v):
            errs.append(f"flag '{k}' must be YYYY-MM-DD")
    useful = p.get("label") not in ("SKIP", "STALE", None)
    if p.get("summary") and not useful:
        errs.append("summary is not used on SKIP items (give a reason instead)")
    if useful and not p.get("summary"):
        errs.append("every non-SKIP item needs a summary (what happened + why it matters)")
    if p.get("background") and not p.get("follows"):
        errs.append("background is only for follow-ups (set follows to the earlier item id)")
    if p.get("follows") and not p.get("background"):
        errs.append("a follow-up needs background: what happened before, with the date")
    if p.get("background") and len(p["background"]) > 300:
        errs.append("background must be under 300 characters")
    notes = p.get("notes")
    if notes is not None and (not isinstance(notes, str) or len(notes) > 6000):
        errs.append("notes must be text under 6000 characters")
    acts = p.get("actions")
    if acts is not None and (not isinstance(acts, list) or len(acts) > 15 or not all(isinstance(x, str) for x in acts)):
        errs.append("actions must be a list of up to 15 short sentences")
    if notes and not useful:
        errs.append("notes are not used on SKIP items")
    deep = p.get("label") == "MAKE" or (p.get("importance") or 0) >= 4 or (role == "competitor" and useful)
    if deep and not notes:
        errs.append("MAKE, importance 4-5 and competitor items need notes (your observations from the full read)")
    imp = p.get("importance")
    if imp is not None and (not isinstance(imp, int) or not 1 <= imp <= 5):
        errs.append("importance must be an integer 1-5")
    if useful and role != "competitor":
        if imp is None:
            errs.append("non-SKIP items need importance 1-5")
        if "category" in cfg["flags"] and not (p.get("flags") or {}).get("category"):
            errs.append("non-SKIP items need flags.category")
    return errs


def main(argv):
    entity = argv[0]
    edir = ENTITIES / entity
    cfg = read_json(edir / "config.json")
    runs = list(load_runs(edir))
    where, roles, titles = {}, {}, {}
    for ddir, items, _ in runs:
        for it in items:
            iid = it["id"]
            where[iid], roles[iid], titles[iid] = ddir, it.get("role", "news"), it.get("title", "")

    if "--mark-stale" in argv:
        days = int(argv[argv.index("--days") + 1]) if "--days" in argv else cfg.get("filters", {}).get("stale_after_days", 7)
        _, stale = pending_for(edir, days)
        payloads = [{"id": it["id"], "label": "STALE"} for it in stale]
        orphaned_dups = {}
    else:
        payloads = json.loads(open(argv[1]).read())
        orphaned_dups = _find_orphaned_duplicates(payloads, roles, titles, runs[:5])

    by_dir, rejected = {}, 0
    for p in payloads:
        iid = p.get("id")
        if iid not in where:
            print(f"✗ {iid}: unknown item id")
            rejected += 1
            continue
        errs = validate(p, cfg, roles[iid])
        if p.get("follows") and p["follows"] not in where:
            errs.append(f"follows '{p['follows']}' is not a known item id")
        if iid in orphaned_dups:
            bg = orphaned_dups[iid]
            errs.append(f"orphaned SKIP(duplicate) for '{bg}' — multiple sources reported it with 0 non-competitor items kept; keep the best primary source as MAKE/KNOW first")
        if errs:
            print(f"✗ {iid}: " + "; ".join(errs))
            rejected += 1
            continue
        if p.get("summary"):
            p["summary"] = p["summary"][:300]
        p["analyzed_at"] = iso(now_utc())
        by_dir.setdefault(where[iid], {})[iid] = {k: v for k, v in p.items() if k != "id"}

    saved = 0
    for ddir, new in by_dir.items():
        current = read_json(ddir / "analysis.json", {})
        current.update(new)
        write_json(ddir / "analysis.json", current)
        saved += len(new)
    print(f"saved {saved}, rejected {rejected}")
    sys.exit(1 if rejected else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
