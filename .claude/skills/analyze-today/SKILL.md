---
name: analyze-today
description: Analyse Signal Hub's pending news items for every niche (label, flag, summarise), save, validate, commit, push and report. Use when the user says "analyze today", "run", "proceed" or "analyse" in the signal-hub repo.
---

# Analyze today

Follow procedure **A** in `AGENTS.md` at the repo root. It is the source of truth. In short:

1. `git pull --rebase`
2. `python3 engine/status.py`
3. `python3 engine/pending.py`
4. For each niche with pending items: read `entities/<niche>/brief.md`, label every item into `work/payloads-<niche>.json`, then run `python3 engine/save_analysis.py <niche> work/payloads-<niche>.json` and fix any rejected items
5. `python3 engine/save_analysis.py <niche> --mark-stale` if stale items were reported
6. `python3 engine/check.py`
7. `git add entities && git commit -m "analysis: <date> (<N> items)" && git push` (if rejected: `git pull --rebase && git push`)
8. Report: counts per niche, MAKE list (NOW first, with angle), IMPORTANT titles, competitor highlights, broken sources, and the dashboard link https://rajesh1215.github.io/signal-hub/

Do it end to end without asking for confirmation.
