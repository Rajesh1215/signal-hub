"""What people in India are searching for: new Google / YouTube search suggestions.

Source fields:
  {"adapter": "site:search_demand",
   "terms": ["chatgpt", "gemini", ...],                  # hot names / topics
   "templates": ["how to use {x}", "is {x} free", ...],  # question starters, {x} = a term
   "seeds": ["best ai for", ...],                        # fixed starters (no term)
   "youtube": ["how to use {x}", "best ai for"],         # starters also checked on YouTube
   "gl": "in", "hl": "en", "every_hours": 20}

Search suggestions come from what many people actually type, so a suggestion
that wasn't there before is a new question people want answered. The source
remembers every suggestion it has seen (in its state, 45 days) and reports only
new ones; the first run just records what exists. It runs at most once every
`every_hours` to keep the number of lookups small.
"""
import json
import time
import urllib.parse
from datetime import timedelta

from common import http_get, iso, now_utc, parse_time

GOOGLE = "https://suggestqueries.google.com/complete/search?client=firefox&hl={hl}&gl={gl}&q={q}"
YOUTUBE = "https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&hl={hl}&gl={gl}&q={q}"
KEEP_DAYS = 45


def suggestions(url):
    _, body, _ = http_get(url, timeout=15)
    data = json.loads(body)
    return [s.strip().lower() for s in data[1] if isinstance(s, str)]


def fetch(src, state):
    state = dict(state or {})
    now = now_utc()
    last = parse_time(state.get("last_run"))
    if last and now - last < timedelta(hours=src.get("every_hours", 20)):
        return [], state  # already checked recently
    seen = dict(state.get("seen", {}))
    first_run = not seen
    gl, hl = src.get("gl", "in"), src.get("hl", "en")
    queries = []  # (starter text, must-contain, where)
    for t in src.get("templates", []):
        for x in src.get("terms", []):
            queries.append((t.replace("{x}", x), x, "google"))
    for s in src.get("seeds", []):
        queries.append((s, s.split()[0], "google"))
    for t in src.get("youtube", []):
        for x in (src.get("terms", []) if "{x}" in t else [None]):
            q = t.replace("{x}", x) if x else t
            queries.append((q, x or q.split()[0], "youtube"))

    out, failures = [], 0
    for q, must, where in queries:
        url = (YOUTUBE if where == "youtube" else GOOGLE).format(hl=hl, gl=gl, q=urllib.parse.quote(q))
        try:
            found = suggestions(url)
        except (OSError, ValueError):
            failures += 1
            if failures >= 5:
                raise OSError("search suggestions unavailable (5 failures)")
            continue
        time.sleep(0.4)
        for s in found:
            if must.lower() not in s or s == q:
                continue  # off-topic completions ("is ai" -> "is air fryer healthy") and the query itself
            key = f"{where}:{s}"
            if key in seen:
                seen[key] = iso(now)
                continue
            seen[key] = iso(now)
            if first_run:
                continue
            platform = "YouTube" if where == "youtube" else "Google"
            search_url = ("https://www.youtube.com/results?search_query=" if where == "youtube"
                          else "https://www.google.com/search?q=") + urllib.parse.quote(s)
            out.append({"url": search_url + "#sh-sd",
                        "title": f"New {platform} search in India: \"{s}\"",
                        "published_at": iso(now),
                        "snippet": f"People have started searching \"{s}\" (suggested when typing \"{q}\" on {platform}, India).",
                        "meta": {"search": s, "starter": q, "platform": platform}})
    cutoff = now - timedelta(days=KEEP_DAYS)
    state["seen"] = {k: v for k, v in seen.items() if parse_time(v) and parse_time(v) > cutoff}
    state["last_run"] = iso(now)
    return out, state
