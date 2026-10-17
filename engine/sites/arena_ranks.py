"""Arena (LMArena) rankings: report when the top of a leaderboard changes.

Source fields: {"adapter": "site:arena_ranks", "boards": ["text", "webdev", ...], "top": 10}

Reads Arena's official leaderboard dataset on Hugging Face
(lmarena-ai/leaderboard-dataset, "latest" split, category "overall") and
compares it with the previous snapshot kept in the source's state:
  - a new #1
  - a model entering the top N
  - a model moving 3+ places inside the top N
Each change includes where the model performs: its organisation, licence and
vote count, its category ranks on that board (coding, math, hard prompts,
languages, industries…) and its place on the other tracked boards.
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


SEARCH = "https://datasets-server.huggingface.co/search?dataset=lmarena-ai/leaderboard-dataset&config={}&split=latest&query={}&length=100"


PARQUET = "https://huggingface.co/api/datasets/lmarena-ai/leaderboard-dataset/parquet/{}/latest"
_BOARD = {}


def board_rows(board):
    """All rows (every category) of a board from its parquet file. Needs pyarrow;
    returns None without it, and the rows API + search are used instead."""
    if board in _BOARD:
        return _BOARD[board]
    try:
        import io
        import urllib.request
        import pyarrow.parquet as pq
    except ImportError:
        return None
    rows = None
    for _ in range(2):
        try:
            _, listing, _ = http_get(PARQUET.format(urllib.parse.quote(board)))
            req = urllib.request.Request(json.loads(listing)[0], headers={"User-Agent": "signal-hub/1.0"})
            with urllib.request.urlopen(req, timeout=90) as r:
                rows = pq.read_table(io.BytesIO(r.read())).to_pylist()
            break
        except (OSError, ValueError, KeyError, IndexError):
            time.sleep(5)
    _BOARD[board] = rows
    return rows


def top_of(board, n):
    rows = board_rows(board)
    if rows is None:
        _, body, _ = http_get(API.format(urllib.parse.quote(board)))
        rows = [r["row"] for r in json.loads(body)["rows"]]
    rows = [r for r in rows if r.get("category") == "overall"]
    rows.sort(key=lambda r: r["rank"])
    date = rows[0]["leaderboard_publish_date"] if rows else None
    return date, [{"model": r["model_name"], "org": r.get("organization", ""), "rank": int(r["rank"]),
                   "license": r.get("license", ""), "votes": int(r.get("vote_count") or r.get("observation_count") or 0),
                   "rating": round(r["rating"]) if r.get("rating") else None} for r in rows[:n]]


def nice(cat):
    return cat.replace("industry_", "").replace("_and_", " & ").replace("_", " ")


def profile(board, model, tops):
    """Where a model performs: its category ranks on this board, plus its place on the other boards."""
    parts = []
    full = board_rows(board)
    if full is not None:
        body = json.dumps({"rows": [{"row": r} for r in full if r.get("model_name") == model]})
    else:
        body = None
    for _ in range(0 if body else 2):  # fallback: the search API (slow and flaky on big boards)
        try:
            _, body, _ = http_get(SEARCH.format(urllib.parse.quote(board), urllib.parse.quote(model)), timeout=90)
            break
        except OSError:
            time.sleep(5)
    try:
        if body is None:
            raise ValueError("search unavailable")
        cats = sorted(((int(r["row"]["rank"]), r["row"]["category"]) for r in json.loads(body)["rows"]
                       if r["row"]["model_name"] == model and r["row"]["category"] != "overall"))
        best = [nice(c) for rk, c in cats if rk == 1]
        good = [f"{nice(c)} #{rk}" for rk, c in cats if 2 <= rk <= 3]
        if best:
            parts.append("#1 in " + ", ".join(best[:8]) + (f" (+{len(best) - 8} more)" if len(best) > 8 else ""))
        if good:
            parts.append(", ".join(good[:5]))
        if cats and cats[-1][0] > 3:
            parts.append(f"weakest: {nice(cats[-1][1])} #{cats[-1][0]}")
    except (OSError, ValueError, KeyError):
        pass
    elsewhere = [f"{NAMES.get(b, b)} #{t['rank']}" for b, top in tops.items() if b != board
                 for t in top if t["model"] == model]
    if elsewhere:
        parts.append("also top 10 on " + ", ".join(elsewhere))
    return ". ".join(parts)


def fetch(src, state):
    n = src.get("top", 10)
    out, new_state = [], dict(state or {})
    failed, fetched = [], {}
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
        if top:
            fetched[board] = (date, top)
    tops = {b: t for b, (_, t) in fetched.items()}
    for board, (date, top) in fetched.items():
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
            def who(t):
                score = f", Elo {t['rating']}" if t.get("rating") else ""
                return f"{t['model']} ({t['org']}, {t['license'] or 'license unknown'}{score}, {t['votes']:,} votes)"
            for t in top:
                if t["model"] == leader and leader != old_leader:
                    head = (f"New #1 on Arena {name}: {leader}",
                            f"{who(t)} is now #1 on the {name} leaderboard, ahead of {old_leader}.")
                elif t["model"] not in old:
                    head = (f"Arena {name}: {t['model']} enters the top {n} at #{t['rank']}",
                            f"{who(t)} is new in the top {n} of the {name} leaderboard, at #{t['rank']}.")
                elif old[t["model"]] - t["rank"] >= 3:
                    head = (f"Arena {name}: {t['model']} jumps to #{t['rank']} (was #{old[t['model']]})",
                            f"{who(t)} moved up {old[t['model']] - t['rank']} places on the {name} leaderboard.")
                else:
                    continue
                detail = profile(board, t["model"], tops)
                events.append((head[0], head[1] + (f" Where it performs: {detail}." if detail else "")))
        for title, text in events:
            fp = hashlib.sha1(title.encode()).hexdigest()[:8]
            out.append({"url": f"{page}#sh-{board}-{date}-{fp}", "title": title,
                        "published_at": when, "snippet": text[:600], "meta": {}})
    if failed and len(failed) == len(src.get("boards", [])):
        raise OSError(f"Hugging Face leaderboard data unavailable for all boards: {failed}")
    return out, new_state
