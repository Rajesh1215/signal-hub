---
description: Analyse all pending Signal Hub items, write video ideas, push, and report
---

Read `AGENTS.md` (procedure A) and run it end to end without asking for confirmation. Every step is required:

1. `python3 engine/refresh.py` (fresh news)
2. `python3 engine/sweep.py`: read the listed Reddit pages and X profiles in the browser and add meaningful posts with `engine/add_item.py`
3. `python3 engine/status.py`
4. `python3 engine/pending.py`
5. For each niche: read its `brief.md`, label every item by hand (quick pass), deep-read MAKE/TEST/importance 4–5 items and YouTube videos (`engine/video.py`), link follow-ups, then `python3 engine/save_analysis.py <niche> work/payloads-<niche>.json`
6. **Video ideas for every niche**: write 2–6 ideas to `work/ideas-<niche>.json` and run `python3 engine/save_ideas.py <niche> work/ideas-<niche>.json`
7. `python3 engine/save_analysis.py <niche> --mark-stale` if needed
8. `python3 engine/check.py --run`: it must pass. It fails if a niche has no fresh video ideas or still has pending items
9. `git add entities notes && git commit -m "analysis: <date> (<N> items, <M> ideas)" && git push`
10. Report: counts, MAKE list, Important titles, **new video ideas**, broken sources, dashboard link
