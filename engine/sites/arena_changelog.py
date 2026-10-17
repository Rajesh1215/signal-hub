"""Arena (formerly LMArena) changelog pages: each dated update becomes an item.

Source fields: {"adapter": "site:arena_changelog", "url": "https://arena.ai/company/leaderboard-changelog/"}

The page embeds its content as JSON ("postParagraph" blocks with a date in
"subtitle"); this reads those blocks instead of the HTML headings.
"""
import hashlib
import re
from datetime import datetime, timezone

from common import clean_text, http_get, iso

SUBTITLE = re.compile(r'"subtitle":"([^"]+)"')
SPAN = re.compile(r'"_type":"span","marks":\[[^\]]*\],"text":"((?:[^"\\]|\\.)*)"')


def fetch(src, state):
    _, html, _ = http_get(src["url"])
    body = html.replace('\\"', '"').replace("\\\\", "\\")
    out = []
    for chunk in body.split('"_type":"postParagraph"')[1:]:
        m = SUBTITLE.search(chunk)
        if not m:
            continue  # blocks without a date (page intro) are not updates
        para, date = chunk[:m.start()], m.group(1)
        text = clean_text("".join(SPAN.findall(para)).replace("\\u0026", "&").replace("\\n", " "), 400)
        try:
            day = datetime.strptime(date.strip(), "%B %d, %Y").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if len(text) < 8:
            continue
        fp = hashlib.sha1(f"{date}|{text[:120]}".encode()).hexdigest()[:10]
        out.append({"url": f"{src['url']}#sh-{fp}", "title": f"{src.get('name', 'Arena')}: {text[:140]}",
                    "published_at": iso(day), "snippet": text, "meta": {}})
    return out, {}
