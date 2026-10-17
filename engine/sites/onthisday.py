"""Wikipedia "On this day" events for upcoming dates (anniversary ideas).

Source fields: {"adapter": "site:onthisday", "days_ahead": [7, 14],
                "min_years": 25, "round_only": true}

Looks N days ahead so there is time to make the video before the date.
round_only keeps anniversaries that are multiples of 25 years (or 10 when
the event is under 100 years old), which is when audiences care most.
"""
import json
from datetime import timedelta

from common import IST, clean_text, http_get, now_utc


def _round(years):
    return years % 25 == 0 or (years < 100 and years % 10 == 0)


def fetch(src, state):
    out = []
    today = now_utc().astimezone(IST).date()
    for ahead in src.get("days_ahead", [7, 14]):
        day = today + timedelta(days=ahead)
        url = f"https://en.wikipedia.org/api/rest_v1/feed/onthisday/selected/{day.month:02d}/{day.day:02d}"
        _, body, _ = http_get(url, headers={"Accept": "application/json"})
        for ev in json.loads(body).get("selected", []):
            year = ev.get("year")
            if not isinstance(year, int):
                continue
            years = day.year - year
            if years < src.get("min_years", 25) or (src.get("round_only", True) and not _round(years)):
                continue
            pages = ev.get("pages") or []
            page = (pages[0].get("content_urls", {}).get("desktop", {}).get("page") if pages else None)
            if not page:
                continue
            out.append({
                "url": f"{page}#sh-otd-{day.isoformat()}-{year}",
                "title": f"{day.strftime('%d %b')} = {years} years since: {clean_text(ev.get('text'), 200)}",
                "published_at": None,
                "snippet": clean_text(pages[0].get("extract"), 300),
                "meta": {"anniversary_date": day.isoformat(), "years": years},
            })
    return out, {}
