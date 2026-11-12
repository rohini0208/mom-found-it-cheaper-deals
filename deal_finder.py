"""Mom Found It Cheaper - daily Amazon deal finder.

Pulls public RSS feeds from Slickdeals and DealNews, keeps only Amazon
deals, and writes one list: DEALS.md (readable in the GitHub app) and
deals.html. No Claude, no API keys, standard library only.

Run:  python deal_finder.py
"""

import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

FEEDS = {
    "Slickdeals Frontpage": "https://slickdeals.net/newsearch.php?mode=frontpage&searcharea=deals&searchin=first&rss=1",
    "Slickdeals Popular": "https://slickdeals.net/newsearch.php?mode=popdeals&searcharea=deals&searchin=first&rss=1",
    "Slickdeals Coupons": "https://slickdeals.net/newsearch.php?searchin=first&forumchoice%5B%5D=10&rss=1",
    "DealNews Home & Garden": "https://www.dealnews.com/c196/Home-Garden/?rss=1",
    "DealNews Clothing": "https://www.dealnews.com/c202/Clothing-Accessories/?rss=1",
    "DealNews Health & Beauty": "https://www.dealnews.com/c756/Health-Beauty/?rss=1",
    "DealNews Toys": "https://www.dealnews.com/c186/Gaming-Toys/?rss=1",
}

KEEP_DAYS = 3          # how long a deal stays on the list
MAX_ROWS = 150         # cap the page length
DATA_FILE = Path("data/deals.json")
UA = "Mozilla/5.0 (deal-finder; personal RSS reader)"

PRICE_RE = re.compile(r"\$\s?(\d[\d,]*(?:\.\d{2})?)")
# Real promo codes are written in capitals, e.g. "code: SAVE50XY". The word
# "code" is matched in any case, the code itself only in capitals/digits,
# so seller names like "w/ Code Sunway Direct" are not mistaken for codes.
CODE_RE = re.compile(r"(?i:code|coupon)[:\s]+[\"']?([A-Z0-9]{4,20})\b")
TAG_RE = re.compile(r"<[^>]+>")
ASIN_RE = re.compile(r"amazon\.com/(?:[^\s\"'<>]*?/)?(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})")
HISTORY_FILE = Path("data/price_history.json")
THUMBS_RE = re.compile(r"thumb score:\s*\+?(\d+)", re.I)
WAS_RE = re.compile(r"(?:list price|reg(?:ularly)?\.?|was|originally|retail)\s*:?\s*\$\s?(\d[\d,]*(?:\.\d{2})?)", re.I)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def clean(text):
    return html.unescape(TAG_RE.sub(" ", text or "")).replace("\xa0", " ").strip()


def features_from(raw_html):
    """Bullet points (<li>) from the deal's own description: real product features."""
    items = re.findall(r"<li[^>]*>(.*?)</li>", raw_html or "", re.I | re.S)
    feats = []
    for it in items:
        t = re.sub(r"\s+", " ", clean(it))
        if 6 <= len(t) <= 80 and "$" not in t and "http" not in t.lower():
            feats.append(t)
    return feats[:3]


def parse_feed(source, raw):
    """Return a list of deal dicts from one RSS feed."""
    deals = []
    root = ET.fromstring(raw)
    for item in root.iter("item"):
        title = clean(item.findtext("title"))
        link = (item.findtext("link") or "").strip()
        raw_desc = item.findtext("description") or ""
        # Slickdeals puts the full text in content:encoded
        for child in item:
            if child.tag.endswith("encoded") and child.text:
                raw_desc = child.text
        desc = re.sub(r"\s+", " ", clean(raw_desc))
        blob = f"{title} {desc}".lower()
        if "amazon" not in blob:
            continue
        try:
            when = parsedate_to_datetime(item.findtext("pubDate")).astimezone(timezone.utc)
        except Exception:
            when = datetime.now(timezone.utc)
        price = PRICE_RE.search(title)
        code = CODE_RE.search(f"{title} {desc}")
        thumbs = THUMBS_RE.search(desc)
        # Deal sites wrap Amazon links in encoded redirects (amazon.com%2Fdp%2F...),
        # so decode twice before looking for the product ID.
        decoded = urllib.parse.unquote(urllib.parse.unquote(html.unescape(raw_desc + " " + link)))
        asin = ASIN_RE.search(decoded)
        was = WAS_RE.search(desc)
        deals.append({
            "id": link or title,
            "title": title,
            "price": f"${price.group(1)}" if price else "",
            "code": code.group(1).upper() if code else ("w/ code" if "w/ code" in blob or "promo code" in blob else ""),
            "coupon": "clip coupon" if "clip" in blob and "coupon" in blob else "",
            "asin": asin.group(1) if asin else "",
            "thumbs": int(thumbs.group(1)) if thumbs else 0,
            "was": f"${was.group(1)}" if was else "",
            "features": features_from(raw_desc),
            "new": bool(re.search(r"\b(new release|newly released|just launched|new arrival|2026 model)\b", blob)),
            "bestseller": bool(re.search(r"\b(best ?seller|#1 best)", blob)),
            "desc": desc[:500],
            "source": source,
            "link": link,
            "seen": when.isoformat(),
        })
    return deals


def product_key(d):
    """ASIN when we have it, else a simplified product name."""
    if d.get("asin"):
        return d["asin"]
    name = re.split(r"\s+(?:for\s+)?\$\d", d["title"].lower())[0]
    return re.sub(r"[^a-z0-9 ]", "", name).strip()[:60]


def update_price_history(new):
    hist = json.loads(HISTORY_FILE.read_text()) if HISTORY_FILE.exists() else {}
    for d in new:
        p = PRICE_RE.search(d.get("price", "") or "")
        if not p:
            continue
        value = float(p.group(1).replace(",", ""))
        day = d["seen"][:10]
        rows = hist.setdefault(product_key(d), [])
        if not any(r[0] == day and r[1] == value for r in rows):
            rows.append([day, value])
        rows.sort()
        del rows[:-60]                      # keep the last 60 price points
    HISTORY_FILE.write_text(json.dumps(hist))
    return hist


def load_history():
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text())
    return []


def merge(history, new):
    by_id = {d["id"]: d for d in history}
    seen_titles = {d["title"].lower() for d in history}
    for d in new:
        if d["id"] in by_id or d["title"].lower() in seen_titles:
            continue
        by_id[d["id"]] = d
        seen_titles.add(d["title"].lower())
    cutoff = datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)
    kept = [d for d in by_id.values() if datetime.fromisoformat(d["seen"]) >= cutoff]
    kept.sort(key=lambda d: d["seen"], reverse=True)
    return kept[:MAX_ROWS]


def write_markdown(deals, errors):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Mom Found It Cheaper - Amazon deal list",
        "",
        f"Updated {now} - {len(deals)} Amazon deals from the last {KEEP_DAYS} days, newest first.",
        "",
        "> Before posting: open the deal, check the price is real, then make **your own SiteStripe link**. "
        "Never repost the source link. Add #ad.",
        "",
        "| Found | Deal | Price | Code / coupon | Source |",
        "|---|---|---|---|---|",
    ]
    for d in deals:
        when = datetime.fromisoformat(d["seen"]).strftime("%b %d %H:%M")
        title = d["title"].replace("|", "/")
        extra = " / ".join(x for x in (d["code"], d["coupon"]) if x)
        lines.append(f"| {when} | [{title}]({d['link']}) | {d['price']} | {extra} | {d['source']} |")
    if errors:
        lines += ["", "Feeds that failed this run: " + ", ".join(errors)]
    lines += ["", "Deal data from Slickdeals and DealNews RSS feeds, for personal use."]
    Path("DEALS.md").write_text("\n".join(lines) + "\n")


def write_html(deals):
    rows = []
    for d in deals:
        when = datetime.fromisoformat(d["seen"]).strftime("%b %d %H:%M")
        extra = " / ".join(x for x in (d["code"], d["coupon"]) if x)
        rows.append(
            f"<tr><td>{when}</td><td><a href='{html.escape(d['link'])}'>{html.escape(d['title'])}</a></td>"
            f"<td>{html.escape(d['price'])}</td><td>{html.escape(extra)}</td><td>{html.escape(d['source'])}</td></tr>"
        )
    page = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mom Found It Cheaper - deals</title>
<style>body{{font-family:system-ui,sans-serif;margin:12px}}table{{border-collapse:collapse;width:100%}}
td,th{{border-bottom:1px solid #ddd;padding:6px;font-size:14px;text-align:left;vertical-align:top}}
th{{background:#f4f4f4}}a{{color:#0a58ca}}</style></head><body>
<h2>Mom Found It Cheaper - Amazon deals</h2>
<p>{len(deals)} deals, newest first. Make your own SiteStripe link before posting.</p>
<table><tr><th>Found</th><th>Deal</th><th>Price</th><th>Code / coupon</th><th>Source</th></tr>
{''.join(rows)}</table><p>Data: Slickdeals and DealNews RSS feeds.</p></body></html>"""
    Path("deals.html").write_text(page)


def main():
    new, errors = [], []
    for name, url in FEEDS.items():
        try:
            new += parse_feed(name, fetch(url))
        except Exception as e:  # one bad feed should not stop the rest
            errors.append(name)
            print(f"[warn] {name}: {e}")
    DATA_FILE.parent.mkdir(exist_ok=True)
    update_price_history(new)
    deals = merge(load_history(), new)
    DATA_FILE.write_text(json.dumps(deals, indent=1))
    write_markdown(deals, errors)
    write_html(deals)
    print(f"{len(new)} Amazon deals fetched, {len(deals)} on the list, {len(errors)} feeds failed")


if __name__ == "__main__":
    main()
