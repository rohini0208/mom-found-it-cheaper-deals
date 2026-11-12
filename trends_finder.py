"""Mom Found It Cheaper - free "what's viral" signals.

Collects product buzz from free public feeds and writes data/trends.json:
  - Reddit communities where people post what TikTok/Instagram made them buy
  - camelcamelcamel "Popular Products" (what Amazon shoppers are tracking, with
    "Best Price" / "Good Deal" against the average price)
  - YouTube Shorts from viral_finder.py (data/viral.json), when YT_API_KEY is set
  - community votes already on our own deals (Slickdeals thumbs)

build_site.py then gives each deal a "seen in N places" score.
Standard library only; any feed that fails is skipped.

Run:  python trends_finder.py
"""

import html
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from deal_finder import ASIN_RE, clean, name_words

UA = "Mozilla/5.0 (mom-found-it-cheaper trends reader; personal RSS)"

REDDIT = {
    "TikTok Made Me Buy It (Reddit)": "https://www.reddit.com/r/TikTokMadeMeBuyIt/top/.rss?t=week",
    "Amazon finds (Reddit)": "https://www.reddit.com/r/AmazonFinds/top/.rss?t=week",
    "Shut Up And Take My Money (Reddit)": "https://www.reddit.com/r/shutupandtakemymoney/top/.rss?t=week",
}
CAMEL_PAGES = ["https://camelcamelcamel.com/popular", "https://camelcamelcamel.com/top_drops"]
OUT = Path("data/trends.json")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def items_from(raw):
    """RSS <item> or Atom <entry> -> (title, link, text)."""
    root = ET.fromstring(raw)
    out = []
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        title = link = text = ""
        for c in el:
            t = c.tag.split("}")[-1]
            if t == "title":
                title = clean(c.text)
            elif t == "link":
                link = (c.get("href") or c.text or "").strip()
            elif t in ("description", "content", "summary"):
                text = c.text or ""
        out.append((title, link, text))
    return out


def reddit_signals():
    sigs, status = [], {}
    for name, url in REDDIT.items():
        try:
            items = items_from(fetch(url))
            for rank, (title, link, text) in enumerate(items, 1):
                asin = ASIN_RE.search(html.unescape(text))
                sigs.append({"source": name, "title": title, "link": link,
                             "asin": asin.group(1) if asin else "", "rank": rank})
            status[name] = len(items)
        except Exception as e:
            status[name] = f"error: {str(e)[:80]}"
    return sigs, status


def camel_signals():
    """camelcamelcamel offers RSS for these lists; find the feed link on the page itself."""
    sigs, status = [], {}
    for page in CAMEL_PAGES:
        name = "camelcamelcamel " + ("popular" if "popular" in page else "top price drops")
        try:
            body = fetch(page).decode("utf-8", "ignore")
            m = re.search(r'<link[^>]+type="application/rss\+xml"[^>]+href="([^"]+)"', body) or \
                re.search(r'href="([^"]+)"[^>]*type="application/rss\+xml"', body)
            feed = html.unescape(m.group(1)) if m else page + ".xml"
            if feed.startswith("/"):
                feed = "https://camelcamelcamel.com" + feed
            items = items_from(fetch(feed))
            for rank, (title, link, text) in enumerate(items, 1):
                asin = re.search(r"/product/([A-Z0-9]{10})", link) or ASIN_RE.search(text)
                label = "Best Price" if "best price" in (title + text).lower() else \
                        ("Good Deal" if "good deal" in (title + text).lower() else "")
                sigs.append({"source": name, "title": re.sub(r"\s*\(B0[A-Z0-9]{8}\).*$", "", title),
                             "link": link, "asin": asin.group(1) if asin else "", "rank": rank, "label": label})
            status[name] = len(items)
        except Exception as e:
            status[name] = f"error: {str(e)[:80]}"
    return sigs, status


def youtube_signals():
    p = Path("data/viral.json")
    if not p.exists():
        return [], {"YouTube Shorts": "no data (add YT_API_KEY)"}
    vids = json.loads(p.read_text()).get("videos", [])
    return ([{"source": "YouTube Shorts", "title": v["title"], "link": v["url"], "asin": "",
              "rank": i, "per_hour": v.get("per_hour", 0)} for i, v in enumerate(vids, 1)],
            {"YouTube Shorts": len(vids)})


def load_signals():
    return json.loads(OUT.read_text()).get("signals", []) if OUT.exists() else []


def viral_sources(deal, signals):
    """Names of the places this product is buzzing (empty list if none).
    Same Amazon product ID, or at least 3 shared product-name words making up
    most of the shorter name."""
    words = name_words(deal["title"])
    found = set()
    for s in signals:
        if deal.get("asin") and deal["asin"] == s.get("asin"):
            found.add(s["source"])
            continue
        sw = set(s.get("words", []))
        shared = words & sw
        if len(shared) >= 3 and len(shared) >= 0.6 * min(len(words), len(sw) or 1):
            found.add(s["source"])
    if deal.get("thumbs", 0) >= 30:
        found.add("Slickdeals community")
    for a in deal.get("also", []):
        found.add(a["source"])
    return sorted(found)


def main():
    sigs, status = [], {}
    for fn in (reddit_signals, camel_signals, youtube_signals):
        s, st = fn()
        sigs += s
        status.update(st)
    for s in sigs:
        s["words"] = sorted(name_words(s["title"]))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"updated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
                               "status": status, "signals": sigs}, indent=1))
    print(f"{len(sigs)} trend signals;", status)


if __name__ == "__main__":
    main()
