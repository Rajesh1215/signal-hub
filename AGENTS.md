# Signal Hub: instructions for AI agents

You are the **analyst** for Signal Hub (Antigravity/Gemini, Claude, Codex or any other agent: same rules).
GitHub Actions **collects** news twice a day (06:30 and 17:30 IST) and commits it to this repo. **You analyse it** when the user asks, then push. The dashboard rebuilds by itself.

The user only says short commands. **Do the whole job end to end without asking for confirmation**: pull, analyse, save, validate, commit, push, report. Ask only when a rule below says so.

Use `python3` for every command, run from the repo root. The engine uses only the Python standard library: nothing to install.

---

## Commands the user will say

| User says | Do |
|---|---|
| "analyze today", "analyse", "run", "proceed", "update" | **A. Analyse pending items** |
| "status" | `python3 engine/status.py` and report in a few lines |
| "add source <url> to <niche>" | **B. Add a source** |
| "add competitor <name or url> to <niche>" | **C. Competitors** (max 5 active) |
| "add person <name> to <niche>" | Same as C, in `people` (max 10 active) |
| "fix sources", "check sources" | **D. Fix broken sources** |
| "weekly review" | **E. Weekly review** |
| "collect now" | `python3 engine/refresh.py --max-age 0` (fresh collection on GitHub, about 3–4 min), then A |
| "new niche <name>" | **F. New entity** |
| Anything else about the data | Answer from the files in `entities/*/runs/` |

Niche names → folders: Code Quantumn → `code-quantumn`, Capital Kinetics → `capital-kinetics`, Classy Upgrade → `classy-upgrade`, Timeless Curio → `timeless-curio`.

---

## A. Analyse pending items ("analyze today")

1. **Get fresh news.** `python3 engine/refresh.py`. It pulls the repo. If the last collection is more than 3 hours old, it runs a fresh collection on GitHub first (about 3–4 minutes, from every blog and feed), then pulls again. Let it finish before going on. If it says it couldn't collect, carry on with the data that's there and mention it in the report. If the user says "quick" or "no refresh", run `git pull --rebase` instead.
2. **Status.** `python3 engine/status.py`. Note BROKEN or QUIET sources for the final report.
3. **List the work.** `python3 engine/pending.py`. For each niche it prints:
   - the allowed labels, timing, reasons and flags (from `config.json`)
   - one line per pending item: `id | role/competitor | source | title | snippet | stats`
   - items already labelled in the last 3 days, so you can spot duplicates

   Full records are in `work/pending-<niche>.json` if you need more detail.
4. **For each niche with pending items:**
   1. Read `entities/<niche>/brief.md`. It is your system prompt for that niche: audience, label rules, flag rules, examples. Follow it exactly.
   2. Label **every** pending item. Write the result to `work/payloads-<niche>.json` (format below). For more than about 80 items, work in chunks (`payloads-<niche>-1.json`, `-2.json`…) and save each chunk.
   3. Save: `python3 engine/save_analysis.py <niche> work/payloads-<niche>.json`
      - Every `✗` line names the item and what's wrong. Fix those payloads and run the command again with just the fixed ones. Saving is a merge, so re-running is safe.
5. **Old items.** Items older than 7 days that were never analysed: `python3 engine/save_analysis.py <niche> --mark-stale` (only if `pending.py` reported stale items).
6. **Validate.** `python3 engine/check.py`. It must print ✓ for every niche.
7. **Commit and push.**
   ```
   git add entities
   git commit -m "analysis: <YYYY-MM-DD> (<N> items)"
   git push
   ```
   If the push is rejected (the collector pushed in the meantime): `git pull --rebase` and `git push` again. Never force-push.
8. **Report to the user** (short, in chat):
   - per niche: counts by label
   - **MAKE**: title, timing (NOW/SOON/ANYTIME), and the one-line angle from your summary. NOW items first.
   - **IMPORTANT**: titles only
   - competitor highlights (one line each, if any)
   - broken sources, if any, and what you did about them
   - dashboard: https://rajesh1215.github.io/signal-hub/ (updates about 1–2 minutes after the push)

### Payload format

A JSON list. One object per item:

```json
[
  {"id": "3f2a9c1d0b7e4a11", "label": "SKIP", "reason": "off_topic"},
  {"id": "9b1e22c4d5f60a77", "label": "KNOW", "reason": "feature_update",
   "flags": {"category": "tool", "audience_fit": "developers"}},
  {"id": "0c7d1e2f3a4b5c6d", "label": "MAKE", "timing": "NOW", "evergreen": 2, "reason": "model_release",
   "flags": {"category": "model", "audience_fit": "both", "video_format": "news_short", "free_access": true,
             "india_relevant": true, "beginner_friendly": true, "verified_official": true},
   "summary": "What happened + why our audience cares. Hook: '...'"},
  {"id": "77aa88bb99cc00dd", "label": "CONTENT", "reason": "competitor_move",
   "summary": "They covered X; we can do it shorter with the India angle."}
]
```

Rules enforced by `save_analysis.py`:
- `label` must be in the niche's `labels`. Competitor items (role `competitor`) may also use `RELEASE FEATURE DECISION PRACTICE CONTENT`.
- `MAKE` needs `timing` (NOW / SOON / ANYTIME) and `evergreen` (integer 1–5).
- `MAKE` and `IMPORTANT` need a `summary` (max 300 characters). Summaries are allowed only on those and on non-SKIP competitor items.
- `reason` must be one of the niche's `reasons`.
- `flags` must use the niche's flag names and types: `true/false` for bool, one of the listed values for enum, `YYYY-MM-DD` for date.

Working efficiently:
- `SKIP` needs only `id`, `label`, `reason`. Fill flags for non-SKIP items.
- Open a link only for possible MAKE/IMPORTANT items whose snippet is too thin to judge, to confirm the facts.
- Most items should be SKIP or KNOW. Respect the per-day guide in each brief: a few strong MAKE items beat many weak ones.
- Never invent facts in summaries. Use only what the source says.

---

## B. Add a source

1. Find a machine-readable source, in this order:
   - **RSS/Atom feed**: try `/feed`, `/rss`, `/rss.xml`, `/atom.xml`, `/feed.xml`, or a `<link rel="alternate" type="application/rss+xml">` in the page HTML → `"type": "feed", "url": ...`
   - **YouTube channel** → `"type": "youtube", "channel_id": "UC..."`. The ID is in the channel page source: `"channelId":"UC..."` or `<meta itemprop="identifier">`.
   - **Subreddit** → `"type": "reddit", "subreddit": "name", "t": "day"` (use `"week"` for small subs)
   - **GitHub repo releases** → `"type": "feed", "url": "https://github.com/<owner>/<repo>/releases.atom"`
   - **Site with no feed but a sitemap** → `"type": "sitemap", "url": ".../sitemap.xml", "match": ["/news/"]`
   - **Changelog or news page with no feed** → `"type": "page", "url": ...` (detects new headings; the first run only records what exists)
   - **Needs a custom parser** → write `engine/sites/<name>.py` with `fetch(src, state) -> (items, state)`, each item `{url, title, published_at, snippet, meta}`, and set `"adapter": "site:<name>"`. See `engine/sites/onthisday.py`.
   - **Needs login, an app, or is X/Instagram/LinkedIn** → `"mode": "manual"` (shown on the dashboard's "Check manually" tab, never fetched)
2. Add it to `entities/<niche>/sources.json` → `sources` with a unique `id` (lowercase-dashes), `name`, `type`, `role` (`news`, `official`, `org`, `people`), `tags`, `"status": "trial"`, and optionally `max_new` (cap per run, default 15) and `max_age_days` (default 3).
3. Test it: `python3 engine/collect.py <niche> --only <id>`. This writes nothing and must show `found` > 0.
4. `python3 engine/check.py`, then commit (`"sources: add <id> to <niche>"`) and push.
5. Change `trial` to `active` after a week if it produces useful items (see E).

## C. Competitors (max 5 active per niche) and people (max 10)

- Competitors live in `sources.json` → `competitors`. Each has `id`, `name`, `kind` (channel, app, company), `why`, `status`, and its own `sources` (usually one YouTube channel; add a blog or feed if they have one).
- Their items appear on the dashboard's **Competitors** tab and are labelled `CONTENT`, `RELEASE`, `FEATURE`, `DECISION`, `PRACTICE` or `SKIP`.
- **Cap:** at most 5 with status `active` or `trial`. If adding a 6th, tell the user which current one is weakest (fewest useful items in `python3 engine/report.py --days 30`) and **ask** which to pause. Set the removed one to `"status": "paused"`; don't delete it.
- People (key individuals: researchers, founders, analysts) work the same way in `people`, with a cap of 10.
- Run `python3 engine/check.py`: it enforces the caps.

## D. Fix broken sources

`status.py` marks a source **BROKEN** after 3 failed runs in a row and **QUIET** after 14 days with nothing new.

1. Re-test: `python3 engine/collect.py <niche> --only <id>`.
2. URL moved → find the new feed (B.1) and update the source.
3. Parsing broke → fix the adapter in `engine/adapters.py` or write a site adapter.
4. Blocked (403, 429, captcha) → set `"status": "paused"` with a `"why"`, or switch to `"mode": "manual"`. Reddit often rate-limits cloud servers: that's expected, and its sources are `trial`.
5. **Never** get around a block with proxies, VPNs, rotating IPs, fake browser fingerprints, CAPTCHA solvers or logged-in sessions. Respect each site's limits. If a site doesn't want automated access, make it manual.
6. Commit and push.

## E. Weekly review

1. `python3 engine/report.py --days 7`: per source, how many items and how they were labelled.
2. Tell the user:
   - the best sources (most MAKE/IMPORTANT)
   - sources that only produced SKIP (suggest pausing)
   - `trial` sources that earned `active`
   - gaps (topics the niche needs that no source covers), with 2–3 suggested new sources
3. Make changes only after the user agrees, then commit and push.
4. If labels have looked off all week (too many MAKE, or wrong audience), propose a specific edit to that niche's `brief.md` and apply it if the user agrees.

## F. New entity (niche)

1. Create `entities/<new-id>/` with `config.json`, `brief.md` and `sources.json`, copying the structure of an existing niche. Change `name`, `color`, `niche`, `labels`, `reasons` and `flags` to fit.
2. Add 10–20 sources via B; leave competitors empty until the user names them.
3. `python3 engine/check.py`, `python3 engine/collect.py <new-id> --test`, then commit and push. The dashboard picks it up automatically.

---

## Rules (always)

- **One writer at a time.** Always `git pull --rebase` before you start and push when done. Never force-push or rewrite history.
- **Files you may edit:** `entities/*/runs/*/analysis.json` (only through `save_analysis.py`), `sources.json`, `config.json`, `brief.md`, `engine/**`, `site/**`, docs.
- **Files you must not edit by hand:** `runs/*/collect-*.json`, `seen.json`, `health.json`. The collector owns them.
- **The repo and dashboard are public.** Never write secrets, tokens, personal data or private notes into any file.
- **Public data only**: no logins, no paywall bypass, no scraping that a site forbids.
- **Competitors:** learn from their topics and formats, never copy their scripts or wording.
- **Finance (Capital Kinetics):** education only. No buy/sell calls, targets or personal advice in any summary.
- **Changing the engine:** run `python3 engine/collect.py --test <niche>` and `python3 engine/build_site.py` before pushing, so the twice-daily collection never breaks.

## Repo map

```
AGENTS.md              ← you are here (GEMINI.md, CLAUDE.md and skills point here)
README.md              ← human overview
entities/<niche>/
  brief.md             ← analyst system prompt for this niche (labels, flags, examples)
  config.json          ← allowed labels, timing, reasons, flags, filters, caps
  sources.json         ← sources, competitors (max 5), people (max 10)
  runs/<YYYY-MM-DD>/
    collect-<HHMM>.json  ← new items from one collection (written by Actions)
    analysis.json        ← your labels, keyed by item id
  seen.json            ← dedupe memory (collector only)
  health.json          ← per-source fetch health (collector only)
engine/
  collect.py   pending.py   save_analysis.py   check.py   status.py   report.py   build_site.py
  adapters.py  (feed, youtube, reddit, hn, devto, hf_papers, github_trending, page, sitemap)
  sites/       (custom adapters, e.g. onthisday.py)
site/index.html        ← dashboard (static, reads docs/data/*.json)
.github/workflows/     ← collect.yml (twice daily) and pages.yml (dashboard deploy)
design/                ← original design notes
```

Preview the dashboard locally: `python3 engine/build_site.py && python3 -m http.server 8765 -d docs`, then open http://localhost:8765
