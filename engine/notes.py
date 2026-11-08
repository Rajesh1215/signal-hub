"""Manage channel-level notes, decisions, to-dos and item notes.

    python3 engine/notes.py <niche>                         # view all notes, decisions & todos
    python3 engine/notes.py <niche> --todo "task text"      # add a to-do item
    python3 engine/notes.py <niche> --done "id or words"    # mark a to-do as completed
    python3 engine/notes.py <niche> --delete-todo "id"      # delete a to-do item
    python3 engine/notes.py <niche> --decision "decision"   # record a strategic channel decision
    python3 engine/notes.py <niche> --note "text"           # set or append channel strategy notes
    python3 engine/notes.py <niche> --item <id> "note"      # add note to a specific news item
    python3 engine/notes.py <niche> --import-json '<json>'  # import/sync notes from the web dashboard
"""
import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from common import ROOT, entity_dirs, read_json, write_json


def get_entity_path(niche):
    for edir in entity_dirs():
        if edir.name == niche or niche in edir.name:
            return edir
    print(f"Error: unknown niche '{niche}'", file=sys.stderr)
    sys.exit(1)


def load_notes(edir):
    p = edir / "user_notes.json"
    data = read_json(p, {})
    if not isinstance(data, dict):
        data = {}
    return {
        "notes": data.get("notes") or "",
        "decisions": data.get("decisions") or [],
        "todos": data.get("todos") or [],
        "item_notes": data.get("item_notes") or {},
        "updated_at": data.get("updated_at") or datetime.now(timezone.utc).isoformat()
    }


def save_notes(edir, data):
    p = edir / "user_notes.json"
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    write_json(p, data)
    try:
        from build_site import main as build_site_main
        build_site_main()
    except Exception as e:
        print(f"Note: build_site failed: {e}", file=sys.stderr)


def print_notes(niche, data):
    print(f"\n=== Notes & Tasks for {niche} ===")
    print(f"Last updated: {data.get('updated_at')}")

    todos = data.get("todos", [])
    print(f"\n--- To-Do Tasks ({len(todos)}) ---")
    if not todos:
        print("  (no to-do tasks)")
    for t in todos:
        status = "[x]" if t.get("done") else "[ ]"
        print(f"  {status} {t.get('text')}  (id: {t.get('id')})")

    decisions = data.get("decisions", [])
    print(f"\n--- Decisions & Rules ({len(decisions)}) ---")
    if not decisions:
        print("  (no decisions recorded)")
    for d in decisions:
        print(f"  • {d.get('text')}  ({d.get('date', '')})")

    notes = data.get("notes", "").strip()
    print(f"\n--- Strategic Channel Notes ---")
    if notes:
        for line in notes.splitlines():
            print(f"  {line}")
    else:
        print("  (none)")

    item_notes = data.get("item_notes", {})
    print(f"\n--- Item Notes ({len(item_notes)}) ---")
    if not item_notes:
        print("  (no item notes)")
    for item_id, n in item_notes.items():
        print(f"  [{item_id}]: {n}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Manage user notes, decisions, and tasks")
    parser.add_argument("niche", help="Channel name or folder (e.g. code-quantumn)")
    parser.add_argument("--todo", help="Add a to-do item")
    parser.add_argument("--done", help="Mark a to-do as completed by id or matching words")
    parser.add_argument("--delete-todo", help="Delete a to-do by id or matching words")
    parser.add_argument("--decision", help="Add a strategic decision")
    parser.add_argument("--delete-decision", help="Delete a decision by id or matching words")
    parser.add_argument("--note", help="Set or append channel note")
    parser.add_argument("--item", nargs=2, metavar=("ITEM_ID", "NOTE"), help="Set note on a specific item")
    parser.add_argument("--import-json", help="Import entire JSON payload from web app export")
    parser.add_argument("--json", action="store_true", help="Output current state as JSON")

    args = parser.parse_args()
    edir = get_entity_path(args.niche)
    data = load_notes(edir)
    changed = False

    if args.import_json:
        try:
            imported = json.loads(args.import_json)
            if isinstance(imported, dict):
                if "notes" in imported:
                    data["notes"] = imported["notes"]
                if "decisions" in imported and isinstance(imported["decisions"], list):
                    data["decisions"] = imported["decisions"]
                if "todos" in imported and isinstance(imported["todos"], list):
                    data["todos"] = imported["todos"]
                if "item_notes" in imported and isinstance(imported["item_notes"], dict):
                    data["item_notes"] = imported["item_notes"]
                changed = True
                print(f"✓ Imported notes for {edir.name}")
        except Exception as e:
            print(f"Error parsing import JSON: {e}", file=sys.stderr)
            sys.exit(1)

    if args.todo:
        tid = "t-" + uuid.uuid4().hex[:6]
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        data["todos"].append({"id": tid, "text": args.todo.strip(), "done": False, "date": today})
        changed = True
        print(f"✓ Added to-do: '{args.todo}' ({tid})")

    if args.done:
        query = args.done.lower()
        found = False
        for t in data["todos"]:
            if t["id"] == args.done or query in t["text"].lower():
                t["done"] = True
                found = True
                print(f"✓ Marked done: '{t['text']}'")
                changed = True
                break
        if not found:
            print(f"Warning: no matching to-do found for '{args.done}'")

    if args.delete_todo:
        query = args.delete_todo.lower()
        before = len(data["todos"])
        data["todos"] = [t for t in data["todos"] if t["id"] != args.delete_todo and query not in t["text"].lower()]
        if len(data["todos"]) < before:
            changed = True
            print(f"✓ Deleted to-do")

    if args.decision:
        did = "d-" + uuid.uuid4().hex[:6]
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        data["decisions"].append({"id": did, "text": args.decision.strip(), "date": today})
        changed = True
        print(f"✓ Recorded decision: '{args.decision}' ({did})")

    if args.delete_decision:
        query = args.delete_decision.lower()
        before = len(data["decisions"])
        data["decisions"] = [d for d in data["decisions"] if d["id"] != args.delete_decision and query not in d["text"].lower()]
        if len(data["decisions"]) < before:
            changed = True
            print(f"✓ Deleted decision")

    if args.note:
        if data["notes"]:
            data["notes"] += "\n" + args.note.strip()
        else:
            data["notes"] = args.note.strip()
        changed = True
        print(f"✓ Updated channel notes")

    if args.item:
        item_id, item_note = args.item[0], args.item[1]
        data["item_notes"][item_id] = item_note.strip()
        changed = True
        print(f"✓ Set note for item {item_id}")

    if changed:
        save_notes(edir, data)

    if args.json:
        print(json.dumps(data, indent=2))
    elif not changed or len(sys.argv) <= 2:
        print_notes(edir.name, data)


if __name__ == "__main__":
    main()
