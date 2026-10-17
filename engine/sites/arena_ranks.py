"""Arena (LMArena) rankings: report when the top of a leaderboard changes.

Source fields: {"adapter": "site:arena_ranks", "boards": ["text", "webdev", ...], "top": 10}

Reads Arena's official leaderboard dataset on Hugging Face
(lmarena-ai/leaderboard-dataset, "latest" split, category "overall") and
compares it with the previous snapshot kept in the source's state:
  - a new #1
  - a model entering the top N
  - a model moving 3+ places inside the top N
The first run reports the current top 5 of each board once, then only changes.
"""
import hashlib
import json
import time
import urllib.parse

from common import http_get, iso, parse_time

API = "https://datasets-server.huggingface.co/rows?dataset=lmarena-ai/leaderboard-dataset&config={}&split=latest&offset=0&length=100"
NAMES = {"text": "Text", "webdev": "WebDev (coding)", "vision": "Vision", "agent": "Agent", "search": "Search",
         "text_to_image": "Text-to-Image", "text_to_video": "Text-to-Video", "image_edit": "Image Edit"}
PAGES = {"text": "text", "webdev": "code/webdev", "vision": "vision", "agent": "agent", "search": "search",
         "text_to_image": "text-to-image", "text_to_video": "text-to-video", "image_edit": "image-edit"}


def top_of(board, n):
    _, body, _ = http_get(API.format(urllib.parse.quote(board)))
    rows = [r["row"] for r in json.loads(body)["rows"] if r["row"].get("category") == "overall"]
    rows.sort(key=lambda r: r["rank"])
    date = rows[0]["leaderboard_publish_date"] if rows else None
    return date, [{"model": r["model_name"], "org": r.get("organization", ""), "rank": int(r["rank"])} for r in rows[:n]]


def fetch(src, state):
    n = src.get("top", 10)
    out, new_state = [], dict(state or {})
    failed = []
    for board in src.get("boards", ["text", "webdev"]):
        for attempt in range(2):
            try:
                date, top = top_of(board, n)
                break
            except (OSError, ValueError, KeyError):
                if attempt:
                    date, top = None, []
                    failed.append(board)
                else:
                    time.sleep(5)
        if not top:
            continue
        name = NAMES.get(board, board)
        page = f"https://arena.ai/leaderboard/{PAGES.get(board, board)}"
        prev = (state or {}).get(board)
        new_state[board] = {"date": date, "top": top}
        if prev and prev.get("date") == date:
            continue  # same leaderboard version as last time
        when = iso(parse_time(f"{date}T12:00:00Z"))
        events = []
        if not prev:
            events.append((f"Arena {name} leaderboard: top 5 today",
                           ", ".join(f"{t['rank']}. {t['model']}" for t in top[:5])))
        else:
            old = {t["model"]: t["rank"] for t in prev["top"]}
            leader, old_leader = top[0]["model"], prev["top"][0]["model"] if prev["top"] else None
            if leader != old_leader:
                events.append((f"New #1 on Arena {name}: {leader}",
                               f"{leader} ({top[0]['org']}) is now #1 on the {name} leaderboard, ahead of {old_leader}."))
            for t in top:
                if t["model"] == leader and leader != old_leader:
                    continue  # already reported as the new #1
                if t["model"] not in old:
                    events.append((f"Arena {name}: {t['model']} enters the top {n} at #{t['rank']}",
                                   f"{t['model']} ({t['org']}) is new in the top {n} of the {name} leaderboard, at #{t['rank']}."))
                elif t["model"] != leader and old[t["model"]] - t["rank"] >= 3:
                    events.append((f"Arena {name}: {t['model']} jumps to #{t['rank']} (was #{old[t['model']]})",
                                   f"{t['model']} moved up {old[t['model']] - t['rank']} places on the {name} leaderboard."))
        for title, text in events:
            fp = hashlib.sha1(title.encode()).hexdigest()[:8]
            out.append({"url": f"{page}#sh-{board}-{date}-{fp}", "title": title,
                        "published_at": when, "snippet": text, "meta": {}})
    if failed and len(failed) == len(src.get("boards", [])):
        raise OSError(f"Hugging Face leaderboard data unavailable for all boards: {failed}")
    return out, new_state
