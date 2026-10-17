# 📡 Signal Hub

A free, personal news radar for four content channels. It collects news twice a day, an AI agent labels it when you ask, and a dashboard shows what to make next.

**Dashboard:** https://rajesh1215.github.io/signal-hub/ (works on phone and desktop: Overview with "Make next" picks, Feed, Competitors, Check manually, Sources)

## How you use it

1. Open this folder in **Antigravity** (or Claude Code, or any coding agent).
2. Type: **`analyze today`**
3. The agent does everything: it fetches fresh news from every source right then (2–4 minutes), then labels every waiting item (new and older) for each niche, fully reads the best ones (Make, Test, importance 4–5) to write accurate summaries, saves, pushes, and tells you what to make. The dashboard updates a minute later.

Other things you can say: `status`, `add source <url> to <niche>`, `add competitor <name> to <niche>`, `fix sources`, `weekly review`, `collect now`, `new niche <name>`.
The agent's full manual is in [AGENTS.md](AGENTS.md). Any new chat reads it automatically through `GEMINI.md`, `CLAUDE.md`, `.agent/rules` or `.agents/skills`.

> **Antigravity tip:** allow it to run terminal commands without asking (auto-execute, or allow-list `python3` and `git`) for this workspace, or it will ask you to approve every step.

## How it works

```
 06:30 and 17:30 IST        when you say "analyze today"              always on
┌──────────────────┐   ┌────────────────────────────────────┐   ┌──────────────────┐
│ GitHub Actions   │   │ Agent on your Mac (Antigravity…)   │   │ GitHub Pages     │
│ collect.py       │──▶│ pending → label with brief.md →    │──▶│ dashboard        │
│ (no AI, no keys) │   │ save_analysis → check → git push   │   │ (static, free)   │
└──────────────────┘   └────────────────────────────────────┘   └──────────────────┘
        commits entities/*/runs/…        commits analysis.json         rebuilds on push
```

- **No servers, no database, no API keys, no cost.** The repo is the database (JSON files), Actions is the scheduler, Pages is the website.
- **Dedupe:** every link is normalised (tracking codes removed, YouTube/Reddit/X forms unified) and remembered for 90 days, so nothing shows twice.
- **Health:** every source's fetch history is tracked; 3 failures in a row marks it BROKEN on the dashboard's Sources tab.

## The four niches

| Niche | Folder | Labels |
|---|---|---|
| Code Quantumn (AI & tech) | `entities/code-quantumn` | SKIP · KNOW · MAKE · TEST · STUDY |
| Capital Kinetics (money & markets) | `entities/capital-kinetics` | SKIP · KNOW · MAKE · WATCH |
| Classy Upgrade (style & grooming) | `entities/classy-upgrade` | SKIP · KNOW · MAKE |
| Timeless Curio (curiosity stories) | `entities/timeless-curio` | SKIP · KNOW · MAKE |

- **KNOW** worth knowing, no video · **MAKE** make a video · **TEST** try it first · **STUDY** learn from it later · **WATCH** developing story (finance).

**What every useful (non-SKIP) item gets**

| Field | Meaning |
|---|---|
| `importance` 1–5 | How much people need to know it (5 must know … 1 minor). 4–5 shows as **Important** on the dashboard |
| `summary` | One or two lines: what happened + why it matters. MAKE items end with the video hook |
| `category` | The only flag, for filtering (e.g. model, tool, tax, skincare, space) |
| `timing` + `evergreen` | MAKE only: NOW (24 h) / SOON (this week) / ANYTIME, and how long the video stays useful (1–5) |

SKIP items only get a reason. Competitor videos get CONTENT · RELEASE · FEATURE · DECISION · PRACTICE (max 5 competitors per niche).
**Waiting** (pending) means collected but not analysed yet; **STALE** means never analysed within 7 days.

To change labels or categories, edit the niche's `config.json` (allowed values) and `brief.md` (how to judge), or just ask the agent.

## Sources

Each niche's `sources.json` lists its sources with a role (`official`, `news`, `org`, `people`, `competitor`), tags and status (`active`, `trial`, `paused`).
Supported: RSS/Atom feeds, YouTube channels, Reddit, Hacker News, dev.to, Hugging Face papers, GitHub Trending and releases, sitemaps, and change detection on pages without a feed.
X/Twitter, Instagram, daily.dev and other login-only sites are listed as **manual** on the dashboard's "Check manually" tab. They're never scraped.

## Good to know

- **The repo is public** (free GitHub Pages needs that). Everything in it is public news; never put private notes or keys here.
- GitHub pauses scheduled workflows in a repo that has had no commits for 60 days. Each "analyze today" counts as activity, and if it ever pauses, re-enable it on the Actions tab.
- Reddit often rate-limits cloud servers, so those sources are marked `trial`. The Sources tab shows whether they work.
- Run it by hand any time from the Actions tab → **collect** → *Run workflow* (or say `collect now`).

## Commands (for reference)

```
python3 engine/refresh.py                      # fetch fresh news now (skips if collected <15 min ago)
python3 engine/status.py                       # what's pending, what's broken
python3 engine/pending.py                      # list items to analyse
python3 engine/save_analysis.py <niche> <payloads.json>
python3 engine/check.py                        # validate configs and sources
python3 engine/collect.py <niche> --only <id>  # test one source (writes nothing)
python3 engine/report.py --days 7              # source quality for the weekly review
python3 engine/build_site.py && python3 -m http.server 8765 -d docs   # local preview
```
