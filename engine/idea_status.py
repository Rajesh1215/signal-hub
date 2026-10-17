"""Mark a video idea as made, skipped, to make, or new again (the user decides).

    python3 engine/idea_status.py <niche> <idea id or words from its title> made|skipped|to_make|new [--note "..."]
    python3 engine/idea_status.py <niche> --list            # open ideas (new + to_make)

Status changes are kept in the idea's history, so later follow-ups know which
ideas became videos.
"""
import sys

from common import ENTITIES, iso, now_utc, read_json, write_json

STATUSES = ("new", "to_make", "made", "skipped")


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    edir = ENTITIES / argv[0]
    ideas = read_json(edir / "ideas.json", [])
    if argv[1] == "--list":
        for i in ideas:
            if i.get("status") in ("new", "to_make"):
                print(f"{i['id']:<44} {i['status']:<8} {i['type']:<9} {i['title']}")
        return
    if len(argv) < 3 or argv[2] not in STATUSES:
        sys.exit(f"status must be one of {STATUSES}")
    key, status = argv[1].lower(), argv[2]
    note = argv[argv.index("--note") + 1] if "--note" in argv else ""
    matches = [i for i in ideas if i["id"].lower() == key] or [i for i in ideas if key in i["title"].lower() or key in i["id"].lower()]
    if len(matches) != 1:
        print(f"✗ {len(matches)} ideas match '{argv[1]}':")
        for i in matches[:10]:
            print(f"  {i['id']}  {i['title']}")
        sys.exit(1)
    idea = matches[0]
    idea["status"] = status
    idea["updated_at"] = iso(now_utc())
    idea.setdefault("history", []).append({"at": idea["updated_at"], "event": f"marked {status}", **({"note": note} if note else {})})
    if note:
        idea["status_note"] = note
    write_json(edir / "ideas.json", ideas)
    print(f"✓ {idea['id']}: {status}" + (f" ({note})" if note else ""))


if __name__ == "__main__":
    main(sys.argv[1:])
