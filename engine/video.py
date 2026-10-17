"""Get what a YouTube video actually says, so the agent analyses the content,
not just the title. Tries the methods in order and saves the text to
work/transcripts/<video id>.txt.

    python3 engine/video.py <youtube url>             # 1. direct transcript fetch
    python3 engine/video.py <youtube url> --gemini    # 3. Gemini watches the video (needs a free API key)

Order the agent follows (AGENTS.md, "YouTube videos"):
  1. this script (direct fetch; YouTube often blocks it)
  2. the agent's browser: open the video, "...more" -> "Show transcript", read it
  3. this script with --gemini (needs GEMINI_API_KEY, see below)
  4. title + description only, and say so in the summary

The Gemini key is read from the GEMINI_API_KEY environment variable or from
~/.config/signal-hub/env (a line GEMINI_API_KEY=...). It is never stored in
this repo. Get a free key at https://aistudio.google.com/apikey
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from html import unescape
from pathlib import Path

from common import ROOT, http_get

OUT = ROOT / "work" / "transcripts"
# Tried in order; a model that is busy (503) or out of free quota (429) is skipped.
GEMINI_MODELS = [m for m in os.environ.get("SIGNAL_HUB_GEMINI_MODELS", "").split(",") if m] or [
    "gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-flash-latest", "gemini-2.5-flash", "gemini-3.5-flash-lite"]
PROMPT = ("Summarise this video for a content researcher. Give: 1) what the video is about in 2 sentences, "
          "2) every concrete claim, launch, tool, number or date mentioned, as bullets with timestamps, "
          "3) any products, companies, websites or people it mentions as sources, "
          "4) how the video is structured (hook, sections, ending). Be factual; don't add anything not said.")


def video_id(url):
    m = re.search(r"(?:v=|youtu\.be/|/shorts/|/live/)([\w-]{11})", url)
    return m.group(1) if m else None


def direct(vid):
    """Read the caption track listed in the watch page. Works only when YouTube allows it."""
    _, html, _ = http_get(f"https://www.youtube.com/watch?v={vid}&hl=en",
                          headers={"Accept-Language": "en", "User-Agent": "Mozilla/5.0"})
    m = re.search(r'"captionTracks":(\[.*?\])', html)
    if not m:
        return None, "no captions listed on the page (the video may have none)"
    tracks = json.loads(m.group(1))
    track = next((t for t in tracks if t.get("languageCode", "").startswith("en")), tracks[0])
    _, body, _ = http_get(track["baseUrl"] + "&fmt=json3")
    if not body.strip():
        return None, "YouTube returned an empty transcript (blocked for scripts)"
    events = json.loads(body).get("events", [])
    lines = []
    for e in events:
        text = "".join(s.get("utf8", "") for s in e.get("segs", []) or []).strip()
        if text:
            t = int(e.get("tStartMs", 0) / 1000)
            lines.append(f"[{t // 60}:{t % 60:02d}] {unescape(text)}")
    return ("\n".join(lines), None) if lines else (None, "transcript was empty")


def gemini_key():
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    env = Path.home() / ".config" / "signal-hub" / "env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.strip().startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"')
    return None


def gemini(url):
    key = gemini_key()
    if not key:
        return None, "no Gemini key (add GEMINI_API_KEY to ~/.config/signal-hub/env)"
    body = json.dumps({"contents": [{"parts": [{"file_data": {"file_uri": url}}, {"text": PROMPT}]}]}).encode()
    errors = []
    for model in GEMINI_MODELS:
        for attempt in range(2):
            req = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                data=body, headers={"Content-Type": "application/json", "x-goog-api-key": key})
            try:
                with urllib.request.urlopen(req, timeout=300) as r:
                    data = json.loads(r.read())
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 503) and attempt == 0 and e.code != 429:
                    time.sleep(8)
                    continue
                errors.append(f"{model}: {e.code}")
                if e.code in (400, 401, 403):
                    return None, f"Gemini rejected the request ({e.code}): {e.read().decode(errors='replace')[:200]}"
                break
            except OSError as e:
                errors.append(f"{model}: {type(e).__name__}")
                break
            parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
            text = "\n".join(p.get("text", "") for p in parts).strip()
            if text:
                return f"model: {model}\n\n{text}", None
            errors.append(f"{model}: empty answer")
            break
    return None, "all Gemini models busy or out of quota (" + ", ".join(errors) + ")"


def main(argv):
    if not argv:
        sys.exit(__doc__)
    url = argv[0]
    vid = video_id(url)
    if not vid:
        sys.exit(f"not a YouTube video link: {url}")
    method = "gemini" if "--gemini" in argv else "direct"
    try:
        text, why = gemini(url) if method == "gemini" else direct(vid)
    except (OSError, ValueError, KeyError) as e:
        text, why = None, f"{type(e).__name__}: {str(e)[:120]}"
    if not text:
        nxt = ("Next: open the video in your browser and use 'Show transcript'." if method == "direct"
               else "Next: use the title and description, and say 'No transcript available' in the summary.")
        print(f"✗ {method}: {why}\n{nxt}")
        sys.exit(2)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{vid}.txt"
    path.write_text(f"{url}\nmethod: {method}\n\n{text}\n")
    print(f"✓ {method}: {len(text.split())} words saved to {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main(sys.argv[1:])
