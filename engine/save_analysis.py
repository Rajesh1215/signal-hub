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
import sys
from datetime import date

from common import ENTITIES, iso, now_utc, read_json, write_json
from pending import load_runs, pending_for


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
    where, roles = {}, {}
    for ddir, items, _ in load_runs(edir):
        for it in items:
            where[it["id"]], roles[it["id"]] = ddir, it.get("role", "news")

    if "--mark-stale" in argv:
        days = int(argv[argv.index("--days") + 1]) if "--days" in argv else cfg.get("filters", {}).get("stale_after_days", 7)
        _, stale = pending_for(edir, days)
        payloads = [{"id": it["id"], "label": "STALE"} for it in stale]
    else:
        payloads = json.loads(open(argv[1]).read())

    by_dir, rejected = {}, 0
    for p in payloads:
        iid = p.get("id")
        if iid not in where:
            print(f"✗ {iid}: unknown item id")
            rejected += 1
            continue
        errs = validate(p, cfg, roles[iid])
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
