"""Save the agent's video ideas for a niche (merged by id into entities/<niche>/ideas.json).

    python3 engine/save_ideas.py <niche> work/ideas-<niche>.json

Each idea:
  {"id": "2026-10-17-gold-fund-pause",            # date + short slug; reuse an id to update an idea
   "title": "Why your gold SIP just got paused",
   "type": "hype" | "months" | "evergreen",       # hype = only works now; months = useful for weeks/months; evergreen = any time
   "timing": "NOW" | "SOON" | "ANYTIME",
   "angle": "the hook / point of view in one line",
   "outline": ["what to show or say, in order", "..."],   # 2-10 points
   "items": ["<news item id>", ...],              # the news it is based on (one or many)
   "follows_idea": "<earlier idea id>",           # optional: this is a follow-up of an earlier idea
   "follow_up": "part 2" | "update",              # with follows_idea: a new video (part 2) or an update to add
   "background": "what happened before, with dates"   # required with follows_idea
  }
New ideas get status "new". The user changes status with idea_status.py.
"""
import json
import sys

from common import ENTITIES, iso, now_utc, read_json, write_json
from pending import load_runs

TYPES = ("hype", "months", "evergreen")
TIMING = ("NOW", "SOON", "ANYTIME")


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    edir = ENTITIES / argv[0]
    known_items = {it["id"] for _, items, _ in load_runs(edir) for it in items}
    ideas = read_json(edir / "ideas.json", [])
    by_id = {i["id"]: i for i in ideas}
    now = iso(now_utc())
    saved = rejected = 0
    for p in json.loads(open(argv[1]).read()):
        errs = []
        if not p.get("id") or not p.get("title"):
            errs.append("needs id and title")
        if p.get("type") not in TYPES:
            errs.append(f"type must be one of {TYPES}")
        if p.get("timing") not in TIMING:
            errs.append(f"timing must be one of {TIMING}")
        if not p.get("angle"):
            errs.append("needs an angle (the hook in one line)")
        out = p.get("outline")
        if not isinstance(out, list) or not 2 <= len(out) <= 10:
            errs.append("outline must be a list of 2-10 points")
        missing = [i for i in p.get("items", []) if i not in known_items]
        if missing:
            errs.append(f"unknown item ids {missing}")
        if p.get("follows_idea"):
            if p["follows_idea"] not in by_id:
                errs.append(f"follows_idea '{p['follows_idea']}' is not an existing idea")
            if not p.get("background"):
                errs.append("a follow-up needs background (what happened before)")
            if p.get("follow_up") not in ("part 2", "update"):
                errs.append("follow_up must be 'part 2' or 'update'")
        if errs:
            print(f"✗ {p.get('id')}: " + "; ".join(errs))
            rejected += 1
            continue
        old = by_id.get(p["id"])
        idea = {**(old or {"status": "new", "created_at": now, "history": []}), **p, "updated_at": now}
        if old:
            idea["items"] = list(dict.fromkeys(old.get("items", []) + p.get("items", [])))
            idea["history"] = old.get("history", []) + [{"at": now, "event": "updated by agent"}]
        by_id[p["id"]] = idea
        saved += 1
    write_json(edir / "ideas.json", sorted(by_id.values(), key=lambda i: i.get("created_at", ""), reverse=True))
    print(f"saved {saved} idea(s), rejected {rejected}")
    sys.exit(1 if rejected else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
