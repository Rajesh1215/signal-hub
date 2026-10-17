# Signal Hub: data model and storage requirements

Last updated: 17 October 2026 · Status: proposal

## Requirements

| # | Requirement | Why |
| --- | --- | --- |
| 1 | **No duplicates:** one item per entity per canonical URL; re-running a job adds nothing | Daily and 2–3-hourly runs overlap |
| 2 | **URL normalisation** before saving (strip `utm_*`, trailing slashes, mobile domains; `youtu.be/x` → `youtube.com/watch?v=x`) | The same link arrives in different forms |
| 3 | **Story clustering:** group items about the same story from different sources | Needed for duplicate rates and a "one story, many sources" view |
| 4 | **Flexible fields:** a JSON `flags` and `meta` field per item, `settings` per entity | Each entity tracks different things without schema changes |
| 5 | **Analysis history:** keep each AI labelling with its model and prompt version | Profiles change; re-analysis must not erase the past |
| 6 | **Your corrections:** store your label overrides | The weekly review uses them to tune profiles |
| 7 | **Source health:** last fetch, ETag/Last-Modified, error count, 30-day stats | Polite fetching and auto-pausing weak sources |
| 8 | **Caps:** max 5 competitors and about 10 key people per entity | Keeps tracking focused |
| 9 | **Run log:** every job's counts, errors and cost | Debugging and staying inside free limits |
| 10 | **One writer at a time** | Overlapping jobs must queue, not collide |
| 11 | **UTC timestamps; dashboard shows IST** | No timezone confusion |
| 12 | **Retention:** keep labelled items forever; delete SKIP item details after 30 days but keep their IDs for dedupe | Small storage, no re-processing |
| 13 | **Privacy:** personal entities (jobs, general) not on the public dashboard | Free GitHub Pages is public |
| 14 | **Backups:** daily export | Never lose the history |
| 15 | **Readable by every tool:** GitHub Actions, the dashboard, Claude and Antigravity | Everyone works on the same data |

## Tables

| Table | Key fields |
| --- | --- |
| `entities` | id, name, profile_md (path), settings JSON, active, created_at |
| `sources` | id, entity_id, role (news, official, people, org, competitor), type (rss, api, page, youtube, reddit, hn, github, hf, x_manual…), url, mode (auto or manual), status (active, trial, paused, disabled, candidate), added_by (user or ai), competitor_id or person_id (optional), last_fetched_at, etag, last_modified, error_count, stats JSON |
| `competitors` | id, entity_id, name, kind (app, channel, company), why, score, status, added_at |
| `people` | id, entity_id, name, why, status, added_at |
| `items` | id (hash of canonical URL + entity), entity_id, source_id (null if pasted), url, canonical_url, content_type, title, published_at, found_at, meta JSON (views, score, stars…), status (new, analyzed, reviewed, done, archived), cluster_id |
| `analyses` | id, item_id, model, prompt_version, label, timing, evergreen, importance, summary, why, flags JSON, created_at |
| `clusters` | id, entity_id, title, first_seen, item_count |
| `inbox` | id, url, entity_hint, note, added_by, added_at, processed |
| `feedback` | id, item_id, your_label, note, created_at |
| `runs` | id, job (collect, analyze, discover, health), started_at, finished_at, status, counts JSON, errors JSON, cost JSON |

Indexes: `items(entity_id, found_at)`, `items(canonical_url)`, `analyses(item_id, created_at)`, `analyses(label)`, `sources(entity_id, status)`.

## Size estimate

About 7 entities × ~200 fetched items a day ≈ 1,400 items a day. Full details are kept only for labelled items (roughly 10–20%); SKIP details go after 30 days. Roughly **100–300 MB a year** (estimate).

## Storage options

| Option | Cost | Good for | Limits |
| --- | --- | --- | --- |
| **A. JSON/JSONL files in the GitHub repo** | Free | Start: read-only dashboard, edits through chat | No buttons on the dashboard; simple queries only |
| **B. Cloudflare D1** (SQLite) + Workers + Pages | Free tier (check current limits) | An interactive app: approve sources, mark done, correct labels, search, private entities behind a login | Small setup; daily export for backup |
| C. Supabase (Postgres) | Free tier | Similar to B | Free projects pause after inactivity |
| D. SQLite file on your Mac | Free | Local only | Not reachable by GitHub Actions or the dashboard |

**Recommendation:** start with **A** but use exactly these tables as file shapes (one JSONL file per table per entity), so moving to **B (D1)** is a direct import when you want buttons, private sections or search.
