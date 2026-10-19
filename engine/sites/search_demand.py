"""What people in India are searching for: new Google / YouTube search suggestions.

Source fields:
  {"adapter": "site:search_demand",
   "terms": ["chatgpt", "gemini", ...],                  # hot names / topics
   "templates": ["how to use {x}", "is {x} free", ...],  # question starters, {x} = a term
   "seeds": ["best ai for", ...],                        # fixed starters (no term)
   "youtube": ["how to use {x}", "best ai for"],         # starters also checked on YouTube
   "regions": ["in", "us"], "hl": "en", "every_hours": 20}   # India + US (closest to "global")

Search suggestions come from what many people actually type, so a suggestion
that wasn't there before is a new question people want answered. The source
remembers every suggestion it has seen (in its state, 45 days). Each run makes
one entry per topic: its top searches today, with the ones that are NEW since
earlier runs listed first. It runs at most once every `every_hours`.
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


REGIONS = {"in": "India", "us": "US/global"}


def fetch(src, state):
    state = dict(state or {})
    now = now_utc()
    last = parse_time(state.get("last_run"))
    if last and state.get("v") == 3 and now - last < timedelta(hours=src.get("every_hours", 20)):
        return [], state  # already checked recently
    seen = dict(state.get("seen", {}))
    hl = src.get("hl", "en")
    regions = src.get("regions", [src.get("gl", "in"), "us"])
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

    # topic -> {"where": set(), region: {"top": [...], "new": [...]}}
    groups, failures = {}, 0
    for gl in regions:
        prefix = "" if gl == "in" else f"{gl}:"  # India keys keep their old form
        first_run = not any(k.startswith(prefix) and (gl != "in" or ":" in k and k.split(":", 1)[0] in ("google", "youtube")) for k in seen)
        for q, must, where in queries:
            url = (YOUTUBE if where == "youtube" else GOOGLE).format(hl=hl, gl=gl, q=urllib.parse.quote(q))
            try:
                found = suggestions(url)
            except (OSError, ValueError):
                failures += 1
                if failures >= 8:
                    raise OSError("search suggestions unavailable (8 failures)")
                continue
            time.sleep(0.4)
            topic = must if must in src.get("terms", []) else q
            g = groups.setdefault(topic, {"where": set()})
            r = g.setdefault(gl, {"top": [], "new": []})
            g["where"].add("YouTube" if where == "youtube" else "Google")
            for rank, s_ in enumerate(found):
                if must.lower() not in s_ or s_ == q:
                    continue
                key = f"{prefix}{where}:{s_}"
                if key not in seen and not first_run:
                    r["new"].append(s_)
                seen[key] = iso(now)
                if rank < 3 and s_ not in r["top"]:
                    r["top"].append(s_)  # Google lists the most-searched completions first
    day = now.date().isoformat()
    out = []
    for topic, g in groups.items():
        parts, n_new, counts = [], 0, {}
        for gl in regions:
            r = g.get(gl)
            if not r or not (r["top"] or r["new"]):
                continue
            new = list(dict.fromkeys(r["new"]))
            n_new += len(new)
            counts[REGIONS.get(gl, gl)] = len(new)
            line = f"{REGIONS.get(gl, gl)}: " + (f"NEW: {'; '.join(new[:6])}. " if new else "") + "Top: " + "; ".join(r["top"][:8])
            parts.append(line)
        if not parts:
            continue
        out.append({"url": f"https://www.google.com/search?q={urllib.parse.quote(topic)}#sh-sd-{urllib.parse.quote(topic)}-{day}",
                    "title": f"What people are searching about \"{topic}\" today (India + US/global)" + (f" ({n_new} new)" if n_new else ""),
                    "published_at": iso(now), "snippet": " | ".join(parts)[:900],
                    "meta": {"topic": topic, "new_searches": n_new, "new_by_region": counts, "platforms": sorted(g["where"]),
                             "regions": [REGIONS.get(x, x) for x in regions]}})
    cutoff = now - timedelta(days=KEEP_DAYS)
    state["seen"] = {k: v for k, v in seen.items() if parse_time(v) and parse_time(v) > cutoff}
    state["last_run"], state["v"] = iso(now), 3
    return out, state
