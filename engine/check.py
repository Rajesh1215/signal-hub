"""Validate every entity's config.json and sources.json. Run after any edit.

    python engine/check.py            # all entities
    python engine/check.py code-quantumn
    python engine/check.py --run      # end of "analyze today": also requires no pending items and fresh video ideas

Checks required fields, unique source IDs, known adapters, allowed values and
the caps (max 5 active competitors, max 10 active people). Exit code 1 on errors.
"""
import importlib
import sys
from datetime import timedelta

from adapters import ADAPTERS
from common import IST, entity_dirs, now_utc, parse_time, read_json

STATUSES = {"active", "trial", "paused", "disabled", "candidate"}
ROLES = {"news", "official", "people", "org", "competitor"}
NEEDS = {"feed": "url", "page": "url", "sitemap": "url", "youtube": "channel_id", "reddit": "subreddit",
         "devto": "tag", "gnews": "query"}
FLAG_TYPES = {"bool", "enum", "int", "date"}


def check_entity(edir):
    errs, warns = [], []
    cfg = read_json(edir / "config.json")
    for k in ("name", "labels", "competitor_labels", "timing", "reasons", "flags"):
        if k not in cfg:
            errs.append(f"config.json: missing '{k}'")
    if "SKIP" not in cfg.get("labels", []):
        errs.append("config.json: labels must include SKIP")
    for name, spec in cfg.get("flags", {}).items():
        if spec.get("type") not in FLAG_TYPES:
            errs.append(f"config.json: flag '{name}' has unknown type '{spec.get('type')}'")
        if spec.get("type") == "enum" and not spec.get("values"):
            errs.append(f"config.json: enum flag '{name}' needs 'values'")
    if not (edir / "brief.md").exists():
        errs.append("brief.md is missing")

    doc = read_json(edir / "sources.json", {})
    caps = cfg.get("caps", {})
    seen = set()

    def check_source(s, where, group_role=None):
        sid = s.get("id")
        if not sid:
            errs.append(f"{where}: source without id")
            return
        if sid in seen:
            errs.append(f"{where}: duplicate source id '{sid}'")
        seen.add(sid)
        role = s.get("role", group_role or "news")
        if role not in ROLES:
            errs.append(f"{sid}: role '{role}' not in {sorted(ROLES)}")
        if s.get("status", "active") not in STATUSES:
            errs.append(f"{sid}: status '{s.get('status')}' not in {sorted(STATUSES)}")
        if s.get("mode", "auto") not in ("auto", "manual", "local"):
            errs.append(f"{sid}: mode must be auto, local or manual")
        if s.get("mode", "auto") == "manual":
            if not s.get("url"):
                errs.append(f"{sid}: manual source needs a url")
            return
        kind = s.get("adapter") or s.get("type")
        if kind and kind.startswith("site:"):
            try:
                importlib.import_module(f"sites.{kind.split(':', 1)[1]}")
            except ImportError:
                errs.append(f"{sid}: engine/sites/{kind.split(':', 1)[1]}.py not found")
        elif kind not in ADAPTERS:
            errs.append(f"{sid}: no adapter for type '{kind}' (use one of {sorted(ADAPTERS)} or site:<name>)")
        elif NEEDS.get(kind) and not s.get(NEEDS[kind]):
            errs.append(f"{sid}: type '{kind}' needs '{NEEDS[kind]}'")

    for s in doc.get("sources", []):
        check_source(s, "sources")
    for group, role, cap in (("competitors", "competitor", caps.get("competitors", 5)),
                             ("people", "people", caps.get("people", 10))):
        active = [g for g in doc.get(group, []) if g.get("status", "active") in ("active", "trial")]
        if len(active) > cap:
            errs.append(f"{group}: {len(active)} active, cap is {cap}. Set the weakest to 'paused' first")
        for g in doc.get(group, []):
            if not g.get("id") or not g.get("name"):
                errs.append(f"{group}: entry needs id and name")
            if not g.get("sources"):
                warns.append(f"{group}/{g.get('id')}: no sources, nothing will be collected")
            for s in g.get("sources", []):
                check_source(s, f"{group}/{g.get('id')}", role)
    return errs, warns


def check_run(edir):
    """After "analyze today": nothing left pending, and fresh video ideas exist
    whenever the niche had useful items in the last day."""
    from pending import load_runs, pending_for
    errs = []
    cfg = read_json(edir / "config.json")
    pending, _ = pending_for(edir, cfg.get("filters", {}).get("stale_after_days", 7))
    if pending:
        errs.append(f"{len(pending)} items still pending: label them (pending.py lists them)")
    now = now_utc()
    useful = 0
    for _, items, analysis in load_runs(edir):
        for it in items:
            a = analysis.get(it["id"])
            at = parse_time((a or {}).get("analyzed_at"))
            if a and at and now - at < timedelta(hours=20) and a.get("label") not in ("SKIP", "STALE"):
                useful += 1
    ideas = read_json(edir / "ideas.json", [])
    fresh = [i for i in ideas if parse_time(i.get("updated_at")) and now - parse_time(i["updated_at"]) < timedelta(hours=20)]
    if useful and not fresh:
        errs.append(f"{useful} useful items analysed today but no video ideas written or updated: "
                    f"write work/ideas-{edir.name}.json and run save_ideas.py (AGENTS.md step 6)")
    return errs


def main(argv):
    run = "--run" in argv
    argv = [a for a in argv if a != "--run"]
    bad = 0
    for edir in entity_dirs():
        if argv and edir.name not in argv:
            continue
        errs, warns = check_entity(edir)
        if run:
            errs += check_run(edir)
        print(f"{'✓' if not errs else '✗'} {edir.name}" + (f": {len(errs)} error(s)" if errs else ""))
        for e in errs:
            print(f"   ✗ {e}")
        for w in warns:
            print(f"   ! {w}")
        bad += len(errs)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
