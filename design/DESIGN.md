> **Note:** original design notes, kept for reference. What is actually built (collection in GitHub Actions, analysis by a local agent with "analyze today", JSON files in this repo, Pages dashboard) is described in [README.md](../README.md) and [AGENTS.md](../AGENTS.md).

# Signal Hub: design

Last updated: 17 October 2026 · Status: proposal, not built · No Telegram (dashboard + X + chat only)

One system that watches the sources you care about, for any topic, and tells you what matters. Each topic is an **entity** with its own instruction file, sources and labels.

## 0. Chosen setup (17 October 2026)

- **Cloud (GitHub Actions) only collects:** twice a day, runs adapters (code) that extract the relevant data per source type, dedupes, applies code filters (age, engagement), and commits a dated run file. **No AI calls in the cloud.**
- **Analysis is done by an Antigravity agent when you ask**, morning and evening: one command reads the pending run files and each entity's `brief.md`, then writes the payloads (labels and flags, plus a short summary only for MAKE and IMPORTANT items), validates them against the schema, and pushes. A GitHub Action then rebuilds the Pages dashboard automatically.
- **Nothing is urgent:** any skipped day stays "pending" and is analysed next time (oldest first; items older than 7 days are marked stale).
- **Failures:** a failed fetch is retried by the next collection run; broken adapters are flagged on the dashboard and fixed in chat.

### Repo layout

```
signal-hub/
  entities/
    code-quantumn/
      brief.md              # agent instructions: goal, audience, labels, rules
      config.json           # labels, flag schema, caps, filters
      sources.json          # sources with role, type, adapter, status, health stats
      seen.json             # IDs already collected (dedupe across days)
      runs/
        2026-10-17/
          collect-0630.json # items from that run: link + extracted data
          collect-1730.json
          analysis.json     # agent payloads for that day (written when analysed)
    capital-kinetics/ ...
  engine/
    adapters/               # rss, youtube, reddit, hn, github, hf, arxiv, page, sites/<custom>
    collect.py              # runs all active sources for all entities
    build_site.py           # turns run + analysis files into the dashboard
    schema/                 # item and analysis JSON schemas
  .agents/skills/analyze/   # the reusable "analyze pending runs" skill for Antigravity (also usable by Claude)
  docs/                     # generated GitHub Pages dashboard
  .github/workflows/
    collect.yml             # schedule: 06:30 and 17:30 IST
    build-site.yml          # rebuilds Pages whenever analysis files are pushed
```

## 1. Entities

An entity is any topic you name. Creating one means adding a folder with a profile and a source list.

| Entity | Goal | Video-making |
| --- | --- | --- |
| `code-quantumn` | AI and coding news, tools, papers for Indian students and developers | Often (news, tests, explainers) |
| `capital-kinetics` | Know all major finance and market news | Rarely: only big trends (on demand) |
| `classy-upgrade` | Fashion, grooming and style trends | Rarely |
| `timeless-curio` | Science, space and history discoveries and anniversaries | Rarely |
| `general` | Your personal interests | Never (knowledge only) |
| `jobs` (later) | Roles that fit you, and what to study for them | Never |
| `competitor-<app>` (later) | What a competitor app or channel is doing publicly | Never (best practices) |

### Folder layout

```
signal-hub/
  entities/
    code-quantumn/
      profile.md        # the "system prompt": goal, audience, what matters, label rules, timing rules
      sources.json      # every source, with status and health stats
      items/2026-10.jsonl  # every item found, with labels and flags
    capital-kinetics/ ...
  inbox/                # links you send manually (any URL, tagged with an entity)
  docs/                 # the GitHub Pages dashboard (generated)
  engine/               # shared code: collectors, analyzer, discovery, health checks
```

## 2. Labels (shared scale, plus per-entity extras)

| Label | Meaning |
| --- | --- |
| **SKIP** | Not worth reading |
| **KNOW** | Worth knowing; a 1-line summary is enough |
| **IMPORTANT** | Must know; read the full item |
| **MAKE** | Worth a video |

For **MAKE**, the analyzer also sets:

| Field | Values | Meaning |
| --- | --- | --- |
| `timing` | `NOW` / `SOON` / `ANYTIME` | Make it today (news), within a week, or any time (evergreen idea) |
| `evergreen` | 1–5 | How long the video stays useful |

Each entity can add its own labels in `profile.md`: for example TEST (try it first) and STUDY (papers) for Code Quantumn, APPLY for jobs, PRACTICE for competitors.

Every item stores flexible extra flags in a JSON `flags` field, so each entity can track whatever it needs without changing the code.

### Item record

```json
{"id": "hash-of-url", "entity": "code-quantumn", "url": "https://...", "source_id": "hf-daily-papers",
 "title": "...", "published_at": "2026-10-17", "found_at": "2026-10-17T08:00Z",
 "status": "new | analyzed | reviewed | done",
 "label": "MAKE", "timing": "NOW", "evergreen": 2,
 "summary": "one line", "why": "why this label",
 "flags": {"free_for_students": true, "needs_test": true}}
```

Store the link plus a short summary only. That's enough, and it keeps the data tiny.

## 3. The pipeline

| Step | Where | When | What |
| --- | --- | --- | --- |
| **1. Collect** | GitHub Actions (cloud, free) | Daily, plus every 2–3 hours for fast sources | Fetch new items from every active source (RSS, APIs, page changes). Dedupe by ID. Save the links |
| **2. Inbox** | Chat with Claude or Antigravity | Any time | You paste any link (YouTube, Reddit, X post, article) and name the entity; it's checked and added to `inbox/` |
| **3. Analyze (quick pass)** | GitHub Actions + Gemini free API | Right after collecting | Read each new item against the entity's `profile.md` and set the label, timing, evergreen and flags. Items are batched to stay inside free limits |
| **4. Publish** | GitHub Pages | After analysis | Dashboard with entity tabs, labels, filters, search and archive |
| **6. Deep dive** | Local: Antigravity (Gemini) or Claude | When you open the laptop, or on request | Verify MAKE and IMPORTANT items against primary sources, research further, draft scripts |
| **7. Weekly review** | Claude or Antigravity | Weekly | Check label accuracy, tune `profile.md` rules, review source health and discoveries |

## 3b. One link is enough: automatic link handling

Whether an item comes from a source or you paste it, the agent only needs the URL. It detects the type and pulls the right data:

| Link type | What gets pulled | Notes |
| --- | --- | --- |
| YouTube video | Title, description, channel, views, transcript, top comments | Transcripts may be blocked from cloud servers; fetch them locally or fall back to description plus comments |
| Reddit post | Post text, score, **top comments**, plus an AI **discussion summary**: main points, agreement, disagreements, useful tips | Public JSON/RSS at low volume; may need to run locally if Reddit blocks cloud IPs |
| X post | Text, author, date, counts (without login) | Replies need your login; manual |
| Blog, news or article | Full text, author, date | |
| GitHub repo | README, stars, recent releases and activity | |
| Hugging Face model, paper or Space | Description, upvotes or likes, downloads, linked code | Spaces are demo apps |
| arXiv paper or PDF | Title, abstract, authors, linked code | |
| App store page | Description, rating, "What's new" | Public pages only |

The analyzer then labels the item against the entity's `profile.md`. Unsupported: audio-only content such as X Spaces.

## 3c. YouTube account

One personal YouTube account is enough. The dashboard tracks the chosen channels per entity (RSS), so the account is only for browsing and discovery. Use YouTube's topic chips at the top of the home feed to switch between niches; they come from your watch history, so they can't be edited directly.

## 4. Source discovery (AI finds new sources)

- **Weekly, per entity:** AI searches the web for new relevant sources (blogs, YouTube channels, subreddits, newsletters, changelogs, GitHub repos).
- **Checks before adding:** the source is relevant to the profile, has a feed or API, isn't a duplicate of an existing source, and is active (posted recently).
- **Trial status:** new sources start as `trial` for 2 weeks and become `active` automatically if they produce KNOW/IMPORTANT/MAKE items. Otherwise they go back to `candidate`. Optionally, require your one-tap approval first.
- **Items found by AI search** (not from a source) go in like inbox items, and their source is proposed if it's worth following.

## 5. Source health (auto-cleanup)

Each source in `sources.json` tracks:

| Stat | Meaning |
| --- | --- |
| `items_30d` | Items found in the last 30 days |
| `keep_rate` | Share labelled KNOW or above |
| `dup_rate` | Share of its stories already seen from other sources first |
| `errors` | Consecutive fetch failures |
| `added_by` | You or AI discovery |
| `status` | active / trial / paused / disabled |

Rules (to tune): pause a source if its keep rate stays under 5% for 30 days, if its duplicate rate is over 80% (others already cover it), or after 5 failed fetches in a row. A weekly report lists what was paused, and you can re-enable anything.

## 6. Personalised platform feeds (YouTube home, X For You)

- **There's no allowed way to pull your personalised feeds automatically.** YouTube's API doesn't expose recommendations, and X and Instagram forbid scraping.
- **What works:**
  1. Keep separate, niche-tuned accounts (as planned) and browse them yourself.
  2. Anything good: paste the link to Claude or Antigravity, which adds it to the inbox.
  3. **Track specific channels** (including competitors) with their free RSS feeds.
  4. **Track topics** with the YouTube Data API's search, which is free within its daily quota but not personalised.
- **Competitor tracking:** their public channels (RSS plus view counts from the YouTube Data API) and public app-store pages. Labels like PRACTICE ("good practice worth copying") apply.

## 6b. Competitors (max 5 per entity)

Competitors are tracked separately from news sources, because the question is different: not "what's the news?" but "what did they ship, decide or do well?".

### Source roles (tag on every source)

| `role` | Meaning | Examples |
| --- | --- | --- |
| `news` | Where news and trends appear | Company blogs, Hacker News, Reddit, papers |
| `official` | Primary sources for verification | Changelogs, press releases, regulators |
| `competitor` | Belongs to one of the tracked competitors | Their blog, changelog, release notes, YouTube channel, app-store "What's new" |

In `sources.json`, competitor sources sit under the competitor they belong to:

```json
{"competitors": [
  {"id": "comp-1", "name": "Example App", "kind": "app | channel | company",
   "why": "same audience, ships weekly", "added": "2026-10-17", "score": 8,
   "sources": [
     {"id": "comp-1-blog", "role": "competitor", "type": "rss", "url": "..."},
     {"id": "comp-1-changelog", "role": "competitor", "type": "page-change", "url": "..."}
   ]}
]}
```

### What to capture (competitor labels)

| Label | Meaning |
| --- | --- |
| RELEASE | A new version or launch |
| FEATURE | A new capability or service improvement |
| DECISION | A pricing, policy, strategy or partnership change |
| PRACTICE | A good practice worth learning from (product, marketing, content) |
| CONTENT | A content idea or format that worked for them (for channels) |

Each also gets the shared importance (SKIP / KNOW / IMPORTANT). Only helpful items are kept on the dashboard.

### Adding or replacing a competitor (cap: 5)

When you send a link, it's checked against:

1. **Relevance:** same audience or category as the entity.
2. **Activity:** publishes, posts or releases regularly.
3. **Public data:** has a blog, changelog, release notes or channel we can follow legally.
4. **Quality:** worth learning from (growth, product quality, reputation).
5. **Overlap:** not too similar to an existing tracked competitor.

If fewer than 5 are tracked, it's added. If 5 are already tracked, it's compared with the weakest; you decide whether to replace.

### Dashboard

Each entity gets a **Competitors** tab: one timeline per competitor (releases, features, decisions, practices), plus a short monthly summary of what they did and what's worth copying.

Public data only: blogs, changelogs, release notes, app-store pages, public channels. X stays manual.

## 7. Entity-specific notes

- **Code Quantumn:** sources include company blogs, 3 changelogs, Hugging Face papers, GitHub Trending, Hacker News, dev.to, Reddit, YouTube channels. Labels add TEST and STUDY.
- **Capital Kinetics:** mostly KNOW/IMPORTANT. MAKE only when a topic is trending widely or affects many people (on demand). Sources: RBI, SEBI, NSE/BSE, PIB releases, finance news RSS, Finshots.
- **Classy Upgrade, Timeless Curio:** few MAKE items. Mostly trend and anniversary awareness.
- **Jobs (later):** use official job board APIs where public (for example Greenhouse and Lever company boards) and company career pages. LinkedIn scraping isn't allowed.
- **Competitors:** up to 5 per entity (see 6b). Public data only, respecting each platform's terms.

See [DATA-MODEL.md](DATA-MODEL.md) for the storage requirements, tables and database options.

## 8. Interface options

| Phase | Interface | Notes |
| --- | --- | --- |
| Start | **GitHub Pages** (read) + chat with Claude or Antigravity (links in, changes) | Free, no backend. No push alerts: urgent news is caught on X; check the dashboard when convenient |
| Later, if you want buttons (approve source, mark done) on the page | **Cloudflare Pages + Workers + D1** (free tier) | This is when a database becomes useful |

## 9. Limits and rules

- X and daily.dev stay manual (or X's paid API later).
- Only public feeds and official APIs. No scraping around platform blocks.
- Free tiers have limits: Gemini free API rate limits, the YouTube API daily quota, GitHub Actions on a public repo. Batch the AI calls.
- Secrets (Gemini key, YouTube API key) live in GitHub Secrets, never in files.
- On GitHub's free plan the Pages dashboard is public. Fine for public news; keep personal entities (`jobs`, `general`) private by publishing only their counts, or move to a private host later.

## 10. Build phases

| Phase | What | Proof |
| --- | --- | --- |
| 1 | Engine core + `code-quantumn` entity + Pages dashboard | One week of daily digests you find useful |
| 2 | Add `capital-kinetics`, `timeless-curio`, `classy-upgrade` (profiles and sources only) | Each produces sensible labels |
| 3 | Source discovery + source health + weekly report | Sources added and paused automatically, with a report |
| 4 | `jobs` and `competitor-*` entities; interactive UI with D1 if needed | When you need them |
