---
name: analyze-today
description: Analyse Signal Hub's pending news items for every niche (label, flag, summarise), save, validate, commit, push and report. Use when the user says "analyze today", "run", "proceed" or "analyse" in the signal-hub repo.
---

# Analyze today

Follow procedure **A** in `AGENTS.md` at the repo root. It is the source of truth. In short:

1. `python3 engine/refresh.py` (pulls, then collects fresh news from every source on GitHub, 2–4 min; skipped if collected in the last 15 min)
2. `python3 engine/status.py`
3. `python3 engine/pending.py`
4. For each niche with pending items: read `entities/<niche>/brief.md`, label every item into `work/payloads-<niche>.json` (quick pass: judge each item yourself, written by hand, no keyword scripts or default labels), then open and fully read every MAKE/TEST/importance 4–5 item and write its summary from the real page (deep read), then run `python3 engine/save_analysis.py <niche> work/payloads-<niche>.json` and fix any rejected items
5. `python3 engine/save_analysis.py <niche> --mark-stale` if stale items were reported
6. `python3 engine/check.py`
7. `git add entities && git commit -m "analysis: <date> (<N> items)" && git push` (if rejected: `git pull --rebase && git push`)
8. Report: counts per niche, MAKE list (NOW first, with angle), Important titles (importance 4–5), competitor highlights, broken sources, and the dashboard link https://rajesh1215.github.io/signal-hub/

Do it end to end without asking for confirmation.
