"""Source adapters. Each takes a source dict and its health state and returns
(items, new_state). An item is {url, title, published_at, snippet, meta}.

Adapters are plain code: no AI. Add a site-specific adapter under
engine/sites/<name>.py when a page needs custom parsing, and point the source's
"adapter" field at it ("site:<name>").
"""
import hashlib
import importlib
import json
import re
import urllib.parse
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

from common import clean_text, http_get, iso, parse_time


def _local(tag):
    return tag.rsplit("}", 1)[-1].lower()


def _find(el, name):
    for c in el:
        if _local(c.tag) == name:
            return c
    return None


def _findall(el, name):
    return [c for c in el if _local(c.tag) == name]


def _text(el, name):
    c = _find(el, name) if el is not None else None
    return (c.text or "").strip() if c is not None and c.text else ""


IMG_RE = re.compile(r"""<img[^>]+src=["']([^"']+)["']""", re.I)


def _image(n, html):
    """Best thumbnail for a feed entry: media:thumbnail, media:content or an
    image enclosure, else the first <img> in the description HTML."""
    for el in n.iter():
        url = el.get("url") or ""
        if not url.startswith("http"):
            continue
        tag, typ = _local(el.tag), (el.get("type") or "").lower()
        if tag == "thumbnail" or (tag in ("content", "enclosure")
                                  and (el.get("medium") == "image" or typ.startswith("image/"))):
            return url
    m = IMG_RE.search(html or "")
    return m.group(1) if m and m.group(1).startswith("http") else None


JUNK_IMAGE = re.compile(r"/emoji/|avatars\.githubusercontent|gravatar\.com|feedburner|pixel|spacer|1x1", re.I)


def parse_feed(body):
    """RSS 2.0, RDF and Atom (YouTube, Reddit, GitHub, Substack, arXiv)."""
    root = ET.fromstring(body.encode() if isinstance(body, str) else body)
    entries = []
    nodes = [n for n in root.iter() if _local(n.tag) in ("item", "entry")]
    for n in nodes:
        link = ""
        for l in _findall(n, "link"):
            if l.get("href") and l.get("rel", "alternate") == "alternate":
                link = l.get("href")
                break
            if (l.text or "").strip():
                link = l.text.strip()
                break
        if not link:
            link = _text(n, "guid")
        meta = {}
        group = _find(n, "group")  # YouTube media:group
        desc = _text(n, "description") or _text(n, "summary") or _text(n, "content")
        if group is not None:
            desc = desc or _text(group, "description")
            community = _find(group, "community")
            stats = _find(community, "statistics") if community is not None else None
            if stats is not None and stats.get("views"):
                meta["views"] = int(stats.get("views"))
        image = _image(n, desc + _text(n, "encoded"))
        if image and not JUNK_IMAGE.search(image):
            meta["image"] = image
        author = _find(n, "author")
        if author is not None:
            meta["author"] = _text(author, "name") or (author.text or "").strip()
        entries.append({
            "url": link,
            "title": clean_text(_text(n, "title"), 300),
            "published_at": iso(parse_time(_text(n, "published") or _text(n, "pubdate")
                                           or _text(n, "updated") or _text(n, "date"))),
            "snippet": clean_text(desc, 400),
            "meta": meta,
        })
    return entries


def _get(url, state, headers=None):
    status, body, h = http_get(url, headers=headers, etag=state.get("etag"),
                               last_modified=state.get("last_modified"))
    new_state = {"etag": h.get("ETag") or h.get("etag"),
                 "last_modified": h.get("Last-Modified") or h.get("last-modified")}
    return status, body, new_state


# ---------------------------------------------------------------- adapters
def a_feed(src, state):
    status, body, st = _get(src["url"], state)
    if status == 304:
        return [], st
    return parse_feed(body), st


def a_youtube(src, state):
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={src['channel_id']}"
    return a_feed({**src, "url": url}, state)


def a_reddit(src, state):
    sub, sort, t = src["subreddit"], src.get("sort", "top"), src.get("t", "day")
    url = f"https://www.reddit.com/r/{sub}/{sort}/.rss?t={t}&limit={src.get('limit', 15)}"
    items, st = a_feed({**src, "url": url}, {})
    for it in items:  # Reddit links point at the comments page: keep that.
        it["meta"]["subreddit"] = sub
    return items, st


def a_hn(src, state):
    status, body, _ = http_get("https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=60")
    words = [w.lower() for w in src.get("keywords", [])]
    out = []
    for h in json.loads(body)["hits"]:
        title = h.get("title") or ""
        if words and not any(re.search(rf"\b{re.escape(w)}", title.lower()) for w in words):
            continue
        if (h.get("points") or 0) < src.get("min_points", 50):
            continue
        out.append({"url": h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}",
                    "title": title, "published_at": iso(parse_time(h.get("created_at"))),
                    "snippet": "",
                    "meta": {"points": h.get("points"), "comments": h.get("num_comments"),
                             "discussion": f"https://news.ycombinator.com/item?id={h['objectID']}"}})
    return out, {}


def a_devto(src, state):
    tag = urllib.parse.quote(src["tag"])
    status, body, _ = http_get(f"https://dev.to/api/articles?tag={tag}&top=1&per_page={src.get('limit', 10)}")
    out = []
    for a in json.loads(body):
        if (a.get("positive_reactions_count") or 0) < src.get("min_reactions", 10):
            continue
        out.append({"url": a["url"], "title": a["title"], "published_at": a.get("published_at"),
                    "snippet": clean_text(a.get("description"), 300),
                    "meta": {"reactions": a.get("positive_reactions_count"), "comments": a.get("comments_count"),
                             "author": (a.get("user") or {}).get("name")}})
    return out, {}


def a_hf_papers(src, state):
    status, body, _ = http_get(f"https://huggingface.co/api/daily_papers?limit={src.get('limit', 50)}")
    out = []
    for p in json.loads(body):
        paper = p.get("paper", {})
        up = paper.get("upvotes") or 0
        if up < src.get("min_upvotes", 15) and not paper.get("githubRepo"):
            continue
        out.append({"url": f"https://huggingface.co/papers/{paper.get('id')}", "title": paper.get("title", ""),
                    "published_at": paper.get("publishedAt") or p.get("publishedAt"),
                    "snippet": clean_text(paper.get("summary"), 400),
                    "meta": {"upvotes": up, "github": paper.get("githubRepo"),
                             "github_stars": paper.get("githubStars")}})
    return out, {}


def a_github_trending(src, state):
    lang = src.get("language", "")
    status, body, _ = http_get(f"https://github.com/trending/{lang}?since={src.get('since', 'daily')}")
    out = []
    for block in re.findall(r'<article class="Box-row">(.*?)</article>', body, re.S)[: src.get("limit", 15)]:
        m = re.search(r'<h2[^>]*>\s*<a[^>]*href="/([^"]+)"', block)
        if not m:
            continue
        repo = m.group(1).strip()
        desc = re.search(r'<p class="col-9[^"]*">(.*?)</p>', block, re.S)
        today = re.search(r"([\d,]+) stars (today|this week|this month)", block)
        stars_today = int(today.group(1).replace(",", "")) if today else 0
        if stars_today < src.get("min_stars_today", 100):
            continue
        out.append({"url": f"https://github.com/{repo}", "title": repo,
                    "published_at": None, "snippet": clean_text(desc.group(1) if desc else "", 300),
                    "meta": {"stars_today": stars_today}})
    return out, {}


class _Blocks(HTMLParser):
    """Collect (heading, text-after-heading) blocks from an HTML page."""

    def __init__(self):
        super().__init__()
        self.blocks, self.cur, self.in_h, self.skip = [], None, False, 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "footer", "header"):
            self.skip += 1
        if tag in ("h1", "h2", "h3"):
            self.in_h, self.cur = True, {"h": "", "t": ""}
            self.blocks.append(self.cur)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "footer", "header") and self.skip:
            self.skip -= 1
        if tag in ("h1", "h2", "h3"):
            self.in_h = False

    def handle_data(self, data):
        if self.skip or self.cur is None:
            return
        if self.in_h:
            self.cur["h"] += data
        elif len(self.cur["t"]) < 600:
            self.cur["t"] += data


def a_page(src, state):
    """Watch a changelog or news page without a feed: each heading block is an
    entry; blocks whose fingerprint hasn't been seen become new items."""
    status, body, st = _get(src["url"], state)
    if status == 304:
        return [], st
    p = _Blocks()
    p.feed(body)
    out = []
    for b in p.blocks:
        head = clean_text(b["h"], 200)
        text = clean_text(b["t"], 400)
        if len(head) < 3:
            continue
        fp = hashlib.sha1(f"{src['url']}|{head}|{text[:200]}".encode()).hexdigest()[:10]
        out.append({"url": f"{src['url']}#sh-{fp}", "title": f"{src.get('name', '')}: {head}".strip(": "),
                    "published_at": None, "snippet": text, "meta": {"page": src["url"]}})
    return out, st


def a_gnews(src, state):
    """Google News RSS search (public feed). Use for sites that block cloud
    servers or have no feed, e.g. {"type": "gnews", "query": "site:gqindia.com"}."""
    q = urllib.parse.quote(f"{src['query']} when:{src.get('when', '3d')}")
    url = f"https://news.google.com/rss/search?q={q}&hl={src.get('hl', 'en-IN')}&gl={src.get('gl', 'IN')}&ceid={src.get('ceid', 'IN:en')}"
    items, st = a_feed({**src, "url": url}, {})
    for it in items:  # titles end with " - Publisher"; snippets only repeat the title
        it["title"] = re.sub(r"\s+-\s+[^-]{2,60}$", "", it["title"])
        it["snippet"] = ""
    return items, st


def a_sitemap(src, state):
    """Sites without a feed: new URLs in sitemap.xml that match a path prefix.
    Title comes from the URL slug; lastmod is used as the publish time."""
    status, body, st = _get(src["url"], state)
    if status == 304:
        return [], st
    match = src.get("match", [])
    match = [match] if isinstance(match, str) else match
    out = []
    for block in re.findall(r"<url>(.*?)</url>", body, re.S):
        loc = re.search(r"<loc>\s*(.*?)\s*</loc>", block)
        if not loc or (match and not any(m in loc.group(1) for m in match)):
            continue
        url = loc.group(1).strip()
        mod = re.search(r"<lastmod>\s*(.*?)\s*</lastmod>", block)
        slug = urllib.parse.urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
        title = slug.replace("-", " ").replace("_", " ").strip().capitalize()
        out.append({"url": url, "title": f"{src.get('name', '')}: {title}".strip(": "),
                    "published_at": iso(parse_time(mod.group(1))) if mod else None,
                    "snippet": "", "meta": {}})
    return out, st


def a_site(src, state):
    mod = importlib.import_module(f"sites.{src['adapter'].split(':', 1)[1]}")
    return mod.fetch(src, state)


ADAPTERS = {"feed": a_feed, "youtube": a_youtube, "reddit": a_reddit, "hn": a_hn, "devto": a_devto,
            "hf_papers": a_hf_papers, "github_trending": a_github_trending, "page": a_page,
            "sitemap": a_sitemap, "gnews": a_gnews}


def run_adapter(src, state):
    kind = src.get("adapter") or src.get("type")
    if kind and kind.startswith("site:"):
        return a_site(src, state)
    if kind not in ADAPTERS:
        raise ValueError(f"no adapter for type '{kind}'")
    return ADAPTERS[kind](src, state)
