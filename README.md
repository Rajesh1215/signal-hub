# 📡 Signal Hub

A free, personal news radar for four content channels. It collects news twice a day, an AI agent labels it when you ask, and a dashboard shows what to make next.

**Dashboard:** https://rajesh1215.github.io/signal-hub/

## How you use it

1. Open this folder in **Antigravity** (or Claude Code, or any coding agent).
2. Type: **`analyze today`**
3. The agent does everything: pulls the latest news, labels every item for each niche, saves, pushes, and tells you what to make. The dashboard updates a minute later.

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
| Code Quantumn (AI & tech) | `entities/code-quantumn` | SKIP · KNOW · IMPORTANT · MAKE · TEST · STUDY |
| Capital Kinetics (money & markets) | `entities/capital-kinetics` | SKIP · KNOW · IMPORTANT · MAKE · WATCH |
| Classy Upgrade (style & grooming) | `entities/classy-upgrade` | SKIP · KNOW · IMPORTANT · MAKE |
| Timeless Curio (curiosity stories) | `entities/timeless-curio` | SKIP · KNOW · IMPORTANT · MAKE |

**Shared for every niche**
- **MAKE timing:** `NOW` (within 24 h) · `SOON` (this week) · `ANYTIME` (evergreen), plus **evergreen** 1–5.
- **Competitor labels** (max 5 competitors per niche): `RELEASE` · `FEATURE` · `DECISION` · `PRACTICE` · `CONTENT`.
- **STALE:** not analysed within 7 days.
- **Reason codes:** one per item, explaining the label (`model_release`, `tax_change`, `trend`, `anniversary`, `duplicate`…).
- Only MAKE and IMPORTANT items (and competitor items) get a short summary. Everything else is just labels and flags.

### Flags per niche

**Code Quantumn**

| Flag | Values |
|---|---|
| category | model · tool · product · research · changelog · policy · offer · incident · tutorial · opinion · hardware · business |
| audience_fit | students · developers · both · experts_only |
| video_format | news_short · test · explainer · tutorial · comparison · none |
| india_relevant · free_access · open_source · beginner_friendly · needs_test · verified_official | yes / no |

**Capital Kinetics**

| Flag | Values |
|---|---|
| category | markets · rbi_policy · banking · tax · ipo · mutual_funds · insurance · regulation · economy · company_results · global · commodities · personal_finance · scam · business_story |
| personal_impact | emi · tax · savings · investing · salary · prices · insurance · none |
| affects_common_people · india_relevant · regulatory · market_moving · trending_widely · verified_official · needs_care | yes / no |

**Classy Upgrade**

| Flag | Values |
|---|---|
| category | fashion · grooming · skincare · haircare · fitness · confidence · habits · brand_news · industry |
| trend_stage | emerging · peak · fading · evergreen |
| occasion | wedding · festival · office · college · date · summer · monsoon · winter · travel · none |
| gender | men · women · all |
| budget_friendly · india_relevant · educational_angle · science_backed | yes / no |

**Timeless Curio**

| Flag | Values |
|---|---|
| category | space · evolution · human_body · inventions · wars_empires · ancient · mysteries · earth_nature · animals · discovery · what_if |
| visual_potential | high · medium · low |
| anniversary_date | a date (from the "On this day" source, 7 and 14 days ahead) |
| verified_primary · what_if_potential · india_angle · sensitive · surprising_fact | yes / no |

To change labels or flags, edit the niche's `config.json` (allowed values) and `brief.md` (how to judge), or just ask the agent.

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
python3 engine/status.py                       # what's pending, what's broken
python3 engine/pending.py                      # list items to analyse
python3 engine/save_analysis.py <niche> <payloads.json>
python3 engine/check.py                        # validate configs and sources
python3 engine/collect.py <niche> --only <id>  # test one source (writes nothing)
python3 engine/report.py --days 7              # source quality for the weekly review
python3 engine/build_site.py && python3 -m http.server 8765 -d docs   # local preview
```
