"""Shared helpers: paths, time, URL normalisation, IDs, HTTP, JSON."""
import gzip
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENTITIES = ROOT / "entities"
DOCS = ROOT / "docs"
IST = timezone(timedelta(hours=5, minutes=30))
UA = "signal-hub/1.0 (personal news digest; +https://github.com/Rajesh1215/signal-hub)"

TRACKING = re.compile(r"^(utm_|ref$|ref_src$|ref_url$|fbclid$|gclid$|mc_|igshid$|si$|feature$|source$)")


def now_utc():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


def parse_time(value):
    """Parse RSS/Atom/ISO/epoch timestamps into aware UTC datetimes."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc)
    value = value.strip()
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M %z"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def canonical_url(url):
    """Normalise a URL so the same link in different forms gets one ID."""
    url = (url or "").strip()
    if not url:
        return url
    p = urllib.parse.urlsplit(url)
    host = p.netloc.lower().removeprefix("www.").removeprefix("m.").removeprefix("mobile.")
    path = p.path
    query = urllib.parse.parse_qsl(p.query, keep_blank_values=False)
    if host == "youtu.be":
        host, query, path = "youtube.com", [("v", path.strip("/"))], "/watch"
    if host.endswith("youtube.com") and path.startswith("/shorts/"):
        query, path = [("v", path.split("/")[2])], "/watch"
    if host in ("twitter.com", "x.com"):
        host = "x.com"
    if host.endswith("reddit.com"):
        host = "reddit.com"
    query = [(k, v) for k, v in query if not TRACKING.match(k)]
    if host == "youtube.com" and path == "/watch":
        query = [(k, v) for k, v in query if k == "v"]
    path = re.sub(r"/+$", "", path) or "/"
    # Fragments are dropped, except our own "#sh-..." markers (one page, many entries).
    frag = p.fragment if p.fragment.startswith("sh-") else ""
    return urllib.parse.urlunsplit(("https", host, path, urllib.parse.urlencode(sorted(query)), frag))


def item_id(entity, url):
    return hashlib.sha1(f"{entity}|{canonical_url(url)}".encode()).hexdigest()[:16]


# Minimum seconds between two requests to the same host (politeness).
HOST_GAP = {"reddit.com": 10, "github.com": 2}
_last_hit = {}
_blocked = set()  # hosts that rate-limited us twice: skip them for the rest of the run


def _wait_for(host):
    host = host.removeprefix("www.").removeprefix("old.")
    gap = HOST_GAP.get(host, 1)
    wait = _last_hit.get(host, 0) + gap - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_hit[host] = time.monotonic()


def http_get(url, headers=None, etag=None, last_modified=None, timeout=25):
    """GET with conditional headers. Returns (status, body_text, response_headers).
    Paces requests per host and retries once after a 429."""
    h = {"User-Agent": UA, "Accept-Encoding": "gzip", **(headers or {})}
    if etag:
        h["If-None-Match"] = etag
    if last_modified:
        h["If-Modified-Since"] = last_modified
    host = urllib.parse.urlsplit(url).netloc.lower()
    if host in _blocked:
        raise urllib.error.URLError(f"skipped: {host} rate-limited us earlier in this run")
    for attempt in range(2):
        _wait_for(host)
        req = urllib.request.Request(url, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                charset = r.headers.get_content_charset() or "utf-8"
                return r.status, raw.decode(charset, errors="replace"), dict(r.headers)
        except urllib.error.HTTPError as e:
            if e.code == 304:
                return 304, "", dict(e.headers)
            if e.code == 429 and attempt == 0:
                time.sleep(min(int(e.headers.get("Retry-After") or 30), 60))
                continue
            if e.code == 429:
                _blocked.add(host)
            raise


def read_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    return json.loads(path.read_text())


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")


def clean_text(text, limit=500):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"&nbsp;|&#160;", " ", text)
    import html as _h
    text = _h.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def entity_dirs():
    return sorted(d for d in ENTITIES.iterdir() if (d / "config.json").exists())


def flatten_sources(sources_doc):
    """Yield every source with role and competitor/person context attached."""
    for s in sources_doc.get("sources", []):
        yield s
    for group, key in (("competitors", "competitor_id"), ("people", "person_id")):
        for g in sources_doc.get(group, []):
            if g.get("status", "active") not in ("active", "trial"):
                continue
            for s in g.get("sources", []):
                s = dict(s)
                s.setdefault("role", "competitor" if group == "competitors" else "people")
                s[key] = g["id"]
                s.setdefault("name", g.get("name"))
                yield s
