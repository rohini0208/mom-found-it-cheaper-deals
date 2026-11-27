"""Mom Found It Cheaper - the one-place deals website.

Builds site/index.html from the collected data:
  data/deals.json          deals, codes, coupons, votes, features (deal_finder.py)
  data/price_history.json  our own price history per product (deal_finder.py)
  data/viral.json          fastest-growing product Shorts (viral_finder.py)
  data/tested.json         deals YOU marked "Tested today" (tested workflow)

Settings (GitHub repo secrets/variables, optional):
  AMAZON_TAG   your Amazon Associates tracking ID, e.g. yourname-20.
               When set, deals with a known product ID link to Amazon with your tag.
  SITE_URL     the public address of this site (for captions).
"""

import utf8_io  # noqa: F401  (first import: forces UTF-8 text IO so Windows cp1252 can't crash on emoji)
import hashlib
import html
import json
import os


def _sft(_t, _fmt):
    """strftime that works on Windows too: %-d/%-I are glibc-only, Windows needs %#d/%#I."""
    return _t.strftime(_fmt.replace("%-", "%#") if os.name == "nt" else _fmt)
import re
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from deal_finder import is_amazon, no_price_title
from trends_finder import load_signals, viral_sources

SIGNALS = load_signals()

# Amazon's Associates rules only allow prices that come from Amazon's own API.
# "show" (your choice): show feed prices with an "as of" time; "hide": no Amazon prices.
AMAZON_PRICES = os.environ.get("AMAZON_PRICES", "show").strip().lower()


def as_of(iso):
    from zoneinfo import ZoneInfo
    if isinstance(iso, (int, float)):
        t = datetime.fromtimestamp(iso, ZoneInfo("America/New_York"))
    else:
        t = datetime.fromisoformat(iso).astimezone(ZoneInfo("America/New_York"))
    return _sft(t, "%b %-d, %-I:%M %p ET")

DATA = Path("data")
OUT = Path("site")
BRAND = "Mom Found It Cheaper"
REPO = os.environ.get("GITHUB_REPOSITORY", "rohini0208/mom-found-it-cheaper-deals")
TAG = os.environ.get("AMAZON_TAG", "momfounditc08-20").strip()  # Amazon Associates tracking ID
PRICE_RE = re.compile(r"\$\s?(\d[\d,]*(?:\.\d{2})?)")


def load(name, default):
    f = DATA / name
    return json.loads(f.read_text()) if f.exists() else default


def deal_id(d):
    return hashlib.sha1(d["id"].encode()).hexdigest()[:10]


def product_key(d):
    if d.get("asin"):
        return d["asin"]
    name = re.split(r"\s+(?:for\s+)?\$\d", d["title"].lower())[0]
    return re.sub(r"[^a-z0-9 ]", "", name).strip()[:60]


def price_num(s):
    m = PRICE_RE.search(s or "")
    return float(m.group(1).replace(",", "")) if m else None


def badge(d, low):
    if d.get("new"):
        return "New release"
    if d.get("bestseller"):
        return "Best seller"
    if low:
        return "Lowest price we've seen"
    if d.get("thumbs", 0) >= 30:
        return "Community favorite"
    if d.get("thumbs", 0) >= 10:
        return "Trending"
    return ""


META = json.loads(Path("data/product_meta.json").read_text()) if Path("data/product_meta.json").exists() else {}
THUMBS = {}


def _find_photo(deal):
    """Lightweight photo lookup (no PIL/make_videos import, so it works on Cloudflare's build)."""
    P = Path("photos")
    if not P.is_dir():
        return None
    did = hashlib.sha1(deal["id"].encode()).hexdigest()[:10]
    asin = (deal.get("asin") or "").lower()
    title = set(re.sub(r"[^a-z0-9]+", " ", deal["title"].lower()).split())
    best = None
    for f in P.iterdir():
        if f.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            continue
        stem = f.stem.lower()
        if stem == did or (asin and stem == asin):
            return f
        words = [w for w in re.split(r"[^a-z0-9]+", stem) if w]
        if words and all(w in title for w in words) and (best is None or len(words) > best[0]):
            best = (len(words), f)
    return best[1] if best else None


_LC = json.loads(Path("data/link_check.json").read_text()).get("items", {}) if Path("data/link_check.json").exists() else {}
_STOP = set("the a an and of for with in on to by amazon only just from new black friday shipped women men womens mens kids pack pc set".split())


def _words(s):
    return {w for w in re.findall(r"[a-z0-9]+", re.sub(r"&#?\w+;", "", html.unescape(s)).lower()) if w not in _STOP and len(w) > 2}


def _amz_title(d):
    m = META.get(d.get("asin", "")) or {}
    if m.get("v", 0) < 4 or not m.get("title"):
        return ""
    t = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", html.unescape(m["title"]))
    t = re.sub(r"(\w)- (\w)", r"\1-\2", t)                      # "Anti- Fatigue" -> "Anti-Fatigue"
    parts = re.split(r",(?!\d)| \| | - | \(", t)
    t = parts[0]
    if len(t.split()) < 3 and len(parts) > 1 and len(parts[1].split()) <= 3:
        t = f"{t} {parts[1].strip()}"                              # "Crayola Light-Ups - Mummy" keeps its variant
    w = t.split()[:16]
    while w and w[-1].lower().rstrip(",&") in {"by", "for", "with", "and", "or", "the", "a", "an", "of", "to", "in", "on", "&", "w/", "up"}:
        w.pop()
    return " ".join(w)


def link_verified(d):
    """Shared name + price check (verify_link.py) against the live Amazon page."""
    import verify_link
    asin = d.get("asin", "")
    t, p = verify_link.amazon_side(asin, META, _LC)
    m = META.get(asin) or {}
    if re.search(r"unavailable|out of stock|ships within \d+ to \d+ (?:month|week)|temporarily|pre-?order|not available", str(m.get("avail", "")), re.I):
        return False                      # not buyable now at the advertised price (Perplexity QA: Samsung S85H)
    if not (m.get("v", 0) >= 4 and m.get("title")) and re.search(r"^up to|shipped|\.\.\.|\$\d|\bjust\b|\bonly\b", clean_title(d["title"]), re.I):
        return False                      # headline-style title and no Amazon title to replace it
    return verify_link.check(clean_title(d["title"]), d.get("price", ""), t, p)[0]


def _fresh_price(asin):
    """Amazon price read by the Lenovo within 48h, as (now, list, rating, reviews, stamp) or None."""
    import time
    m = META.get(asin) or {}
    if not m.get("now") or not m.get("checked") or time.time() - m["checked"] > 48 * 3600:
        return None
    return m


def _price_html(asin):
    m = _fresh_price(asin)
    if not m:
        return ""
    import time
    was = f' <s style="opacity:.6;font-weight:400">{m["list"]}</s>' if m.get("list") and price_num(m["list"]) and price_num(m["now"]) and price_num(m["list"]) > price_num(m["now"]) else ""
    rt = f' &middot; {m["rating"]:.1f}&#9733; ({m["reviews"]:,})' if m.get("rating") and (m.get("reviews") or 0) >= 100 else ""
    stamp = time.strftime("%b %d", time.localtime(m["checked"]))
    return (f'<b style="font-size:20px;color:#f5c542;font-family:Inter,sans-serif">{html.escape(m["now"])}{was}</b>'
            f'<small style="color:#a99f93">Amazon price as of {stamp}{rt}</small>')


def thumb_for(d):
    """Copy/shrink the product photo into site/photos and return its relative URL (or '')."""
    src = _find_photo(d)
    if not src:
        return ""
    name = f"{deal_id(d)}.jpg"
    dest = OUT / "photos" / name
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            from PIL import Image
            im = Image.open(src).convert("RGB")
            im.thumbnail((520, 520))
            im.save(dest, "JPEG", quality=82)
        except ImportError:
            dest.write_bytes(Path(src).read_bytes())
    except Exception:
        return ""
    return f"photos/{name}"


def savings(d):
    """(list price, pct off, rating, reviews) from verified Amazon data, else blanks."""
    m = META.get(d.get("asin", "")) or {}
    p = price_num(d.get("price"))
    try:
        lst = float(m.get("list"))
    except (TypeError, ValueError):
        lst = None
    pct = 0
    if p and lst and p < lst <= 4 * p:
        pct = round(100 * (1 - p / lst))
    return (lst if pct >= 10 else None), (pct if pct >= 10 else 0), m.get("rating"), m.get("reviews") or 0


def link_for(d):
    """Your own tagged Amazon link when possible; otherwise the source deal page."""
    if TAG and d.get("asin"):
        return f"https://www.amazon.com/dp/{d['asin']}?tag={TAG}", "Get this deal"
    return d["link"], "Get this deal"


def clean_title(t):
    from deal_finder import lead_clean
    t = lead_clean(t)
    t = re.sub(r"^\$[\d,.]+\*?[:|]\s*", "", t)
    t = re.sub(r"\s+(?:at|on|from)\s+Amazon\b.*$|\s+AC$|\s*\+\s*Free (?:S&H|Shipping).*$", "", t, flags=re.I)
    return t.strip() or t


def _checked_label(m):
    """'Checked 7:12 AM ET' from the Lenovo run time, or ''."""
    ts = m.get("checked")
    if not ts:
        return ""
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("America/New_York")
    dt = datetime.fromtimestamp(ts, tz)
    today = datetime.now(tz).date()
    t = _sft(dt, "%-I:%M %p") + " ET"
    return "Checked " + (t if dt.date() == today else ("yesterday " if (today - dt.date()).days == 1 else _sft(dt, "%b %-d ") ) + t)


def _drop_pct(d, history, now_price):
    """% below our own recorded high (>=2 points, real drop) else 0. Our log, not Amazon's."""
    pts = [p for _, p in history.get(product_key(d), [])]
    if now_price is None or len(pts) < 2:
        return 0
    hi = max(pts)
    return int(round(100 * (hi - now_price) / hi)) if hi > now_price else 0


def _lowest_since(d, history, now_price):
    """'Nov 12' if today's Amazon price is at or below every price in our own log (>=2 earlier points), else ''."""
    pts = history.get(product_key(d), [])
    if now_price is None or len(pts) < 2:
        return ""
    lo, hi = min(p for _, p in pts), max(p for _, p in pts)
    if now_price <= lo and hi >= now_price * 1.05:         # a real drop, not a flat line
        first = pts[0][0]
        return _sft(datetime.strptime(first, "%Y-%m-%d"), "%b %-d")
    return ""


def price_block(m, now_price):
    """Show mode: today's Amazon price, Amazon's list price struck through, % off. '' when nothing fresh."""
    if AMAZON_PRICES == "hide" or now_price is None or not m.get("now"):
        return "", 0
    lst = price_num(m.get("list")) if m.get("list") else None
    off = int(round(100 * (lst - now_price) / lst)) if lst and lst > now_price else 0
    was = f'<s>{html.escape(m["list"])}</s>' if off >= 5 else ""
    pct = f'<span class="off">{off}% off</span>' if off >= 10 else ""
    return f'<div class="price"><b>{html.escape(m["now"])}</b>{was}{pct}</div>', off


def card(d, history, tested, rank=0, idsuffix="", in_tier=False):
    import brand
    orig_title = d["title"]
    d = dict(d, title=clean_title(d["title"]))
    i = deal_id(d)
    t = tested.get(i, "")
    if isinstance(t, dict) and t.get("asin") and not d.get("asin"):
        d = dict(d, asin=t["asin"])
    url, label = link_for(d)
    is_amz = is_amazon(d)
    amz = is_amz and AMAZON_PRICES == "hide"
    _mm = META.get(d.get("asin", "")) or {}
    # the number: Amazon's current price from the morning check (owner decision 2026-11-25), else deal price
    now_price = price_num(_mm.get("now")) if _mm.get("v", 0) >= 4 else None   # Amazon check only, never the feed price
    tier_txt = brand.tier(now_price) if now_price is not None else ""
    pct = _drop_pct(d, history, now_price)
    # ONE sticker, from verifiable states only
    low = orig_title.lower()
    promo_low = str(_mm.get("promo", "")).lower()
    lowest = _lowest_since(d, history, now_price)
    price_html, list_off = price_block(_mm, now_price)
    if "black friday" in low or "bf " in low or "black friday" in promo_low or "thanksgiving" in promo_low:
        sticker = "BF DEAL"
    elif lowest and len(history.get(product_key(d), [])) >= 3:
        sticker = "LOWEST YET"
    elif now_price is not None and now_price < 10 and not in_tier:
        sticker = "UNDER $10"
    elif rank == 1:
        sticker = "MIA'S PICK"
    elif pct >= 10:
        sticker = "PRICE DROPPED"
    else:
        sticker = ""
    checked = _checked_label(_mm)
    if checked and AMAZON_PRICES != "hide":
        checked = checked.replace("Checked ", "Amazon price ")        # "Amazon price 7:12 AM ET"
    votes = d.get("thumbs", 0)
    buzz = viral_sources(d, SIGNALS)
    # No third-party names or vote counts on cards (Slickdeals ToS forbids repurposing their content/marks).
    proof2 = "Trending" if len(buzz) >= 2 or votes >= 30 else ""   # no third-party names or counts; our own counts appear via /hit
    why = (d.get("features") or [""])[0]
    ss = "with Subscribe &amp; Save" if re.search(r"S&S|Sub(?:scribe)?\s*(?:&|and)\s*Save", orig_title, re.I) else ""
    code = d.get("code", "")
    real_code = bool(code and code != "w/ code" and code.lower() in str(_mm.get("promo", "")).lower())
    _th = thumb_for(d)
    _at = _amz_title(d)
    _dt = no_price_title(d["title"])
    title = _at if _at and (len(_at.split()) >= 3 or len(_dt.split()) < 3) else (_dt or _at)   # "Mellow Gold" -> fuller deal title
    title = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", title)
    title = re.sub(r"\b(?=[A-Z0-9-]{5,}\b)(?=[A-Z0-9-]*\d)(?=[A-Z0-9-]*[A-Z])[A-Z0-9-]+\b", "", title)   # drop model codes like 32516HD
    title = re.sub(r"\s{2,}", " ", title).strip(" ,-")
    tags = " ".join(filter(None, ["has-code" if real_code else "", "has-coupon" if d.get("coupon") else "",
                                  "under25" if now_price is not None and now_price < 25 else "", "viral" if len(buzz) >= 2 else ""]))
    return f"""
<article class="card {tags}" id="d-{i}{idsuffix}" data-title="{html.escape(title.lower())}" data-cat="{html.escape(d.get('category','Everything else'))}" data-store="{html.escape(d.get('store','Other'))}" data-asin="{html.escape(d.get('asin',''))}">
  <a class="ph" href="{html.escape(url)}" target="_blank" rel="sponsored noopener">{f'<img src="{_th}" loading="lazy" alt="{html.escape(title)}">' if _th else ''}{f'<span class="stk">{sticker}</span>' if sticker else ''}</a>
  {price_html if price_html else (f'<div class="tier">{html.escape(tier_txt)}</div>' if tier_txt and not in_tier else '')}
  <h3>{html.escape(title)}</h3>
  <div class="proof">{f'<span class="chk">&#10003; {checked}</span>' if checked else ''}{f'<span class="fact low">Lowest we&#8217;ve seen since {lowest}</span>' if lowest and AMAZON_PRICES != "hide" else ''}{f'<span class="fact">{proof2}</span>' if proof2 else ''}<span class="fact saved" data-saved="{html.escape(d.get('asin') or i)}"></span></div>
  {f'<div class="why">{html.escape(why)}</div>' if why else ''}

  {f'<button class="code" data-code="{html.escape(code)}">Code <b>{html.escape(code)}</b> <span>tap to copy</span></button>' if real_code else ''}
  {'<div class="why">Clip the coupon on the product page</div>' if d.get('coupon') else ''}
  <a class="go" href="{html.escape(url)}" target="_blank" rel="sponsored noopener" data-track="{html.escape(d.get('asin') or i)}" aria-label="{'Get it on Amazon' if price_html else "See today's price on Amazon"}: {html.escape(title)}">{'Get it on Amazon' if price_html else "See today's price"} &rarr;</a>
  <div class="paid">Paid link &middot; #ad &middot; <span class="chip">{html.escape(d.get('category','Everything else'))}</span></div>
</article>"""


DEEPLINK_JS = ("<script>(function(){var h=location.hash.slice(1);if(!h||document.getElementById(h))return;"
               "var el=document.querySelector('[id^=\"'+h+'-\"]');if(el){el.scrollIntoView({block:'center'});el.classList.add('hit');}})();</script>")


def _short(t, n):
    import textwrap
    t = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", t)
    return textwrap.shorten(t, width=n, placeholder="\u2026")


def _trend_ok(s):
    """Trending tile needs an Amazon title (Lenovo check) that matches the trend title: right product or no tile."""
    import verify_link
    t = (META.get(s["asin"]) or {}).get("title")
    return bool(t) and verify_link.title_score(s["title"], t) >= 0.5


def trending_section():
    """Top products people are talking about right now, from each free source."""
    by_src = {}
    for s in SIGNALS:
        by_src.setdefault(s["source"], []).append(s)
    picks = []
    for src, items in by_src.items():
        have = [s for s in items if s.get("asin") and "gift card" not in s["title"].lower() and _trend_ok(s) and _find_photo({"id": s["link"], "title": s["title"], "asin": s["asin"]})] if AMAZON_PRICES == "hide" else [s for s in items if s.get("asin") and "gift card" not in s["title"].lower() and _fresh_price(s["asin"]) and _find_photo({"id": s["link"], "title": s["title"], "asin": s["asin"]})]
        picks += sorted(have, key=lambda s: s.get("rank", 99))[:3]      # only trends with a real photo
    if not picks:
        return ""
    cells = "".join(
        f'<a class="viral" href="{html.escape(f"https://www.amazon.com/dp/{s['asin']}?tag={TAG}" if TAG and s.get("asin") else s["link"])}" target="_blank" rel="sponsored noopener">'
        + f'<img src="{thumb_for({"id": s["link"], "title": s["title"], "asin": s["asin"]})}" alt="{html.escape(_trend_title(s))}" loading="lazy" style="width:100%;aspect-ratio:4/3;object-fit:contain;background:#fff;border-radius:10px;margin-bottom:8px">' + ("" if AMAZON_PRICES == "hide" else price_block(META.get(s["asin"]) or {}, _amazon_now({"asin": s["asin"]}))[0]) +
        f'<span>Trending</span>'
        f'<em>{html.escape(_trend_title(s))}</em><span class="paid">Paid link &middot; #ad</span></a>' for s in picks[:12])
    return ('<section><h2>Trending right now</h2><p class="sub">What people are buying and talking about '
            'on TikTok, Reddit, YouTube and Amazon</p><div class="virals">' + cells + '</div></section>')


def _trend_title(s):
    """Clean, complete trending title: Amazon's own title (shortened at a natural break), else the feed title cut at a word."""
    t = _amz_title({"asin": s.get("asin", "")}) or re.split(r" \| | - | \(", s["title"])[0]
    t = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", t).strip(" ,&-")
    if len(t) > 70:
        t = t[:70].rsplit(" ", 1)[0].rstrip(" ,&-") + "\u2026"
    return t


def viral_section(viral):
    vids = viral.get("videos", [])[:6]
    if not vids:
        return trending_section()
    items = "".join(
        f'<a class="viral" href="{html.escape(v["url"])}" target="_blank" rel="noopener">'
        f'<b>{v["per_hour"]:,}</b><span>views/hour</span><em>{html.escape(v["title"][:70])}</em></a>'
        for v in vids)
    return f'<section><h2>Going viral this week</h2><p class="sub">Fastest-growing product videos right now</p><div class="virals">{items}</div></section>' + trending_section()


CSS = """
:root{--cream:#FFF6EC;--ink:#1F1A2E;--muted:#60586E;--tang:#C2410C;--yel:#FFC53D;--green:#0F766E;--mint:#D7F3E6;--lav:#EDE7FF;--peach:#FFE8B0;
--ivory:#FFF6EC;--char:#1F1A2E;--gold:#C2410C;--blush:#FFE8B0;--coral:#C2410C;--coral2:#C2410C}
*{box-sizing:border-box}body{margin:0;background:var(--cream);color:var(--ink);font-family:Inter,system-ui,sans-serif;padding-bottom:64px}
a{color:var(--ink)}
header{background:var(--cream);color:var(--ink)}
.hero{max-width:1120px;margin:0 auto;display:grid;grid-template-columns:1.1fr .9fr;align-items:center;gap:8px;padding:22px 20px 0}
.hero-txt{padding:10px 0 30px}
.wordmark{font-family:'Playfair Display',Georgia,serif;font-size:20px;color:var(--ink);margin-bottom:14px}
h1{font-size:64px;line-height:1.02;letter-spacing:-.02em;margin:10px 0 14px;font-weight:800}h1 em{font-style:normal;color:var(--tang)}
.proofline{font-size:16px;color:var(--muted);margin:0 0 12px;max-width:46ch}
.stk{display:inline-block;background:var(--yel);color:var(--ink);font-weight:800;font-size:12px;letter-spacing:.06em;padding:7px 12px;border-radius:30px;transform:rotate(-6deg);border:2px solid #fff;box-shadow:0 3px 8px rgba(31,26,46,.12)}
.hero-stk{font-size:13px;margin-left:4px}
.hero img.scene{width:100%;height:auto;display:block;border-radius:24px}
.join{display:inline-block;margin-top:14px;background:var(--tang);color:#fff;padding:14px 22px;border-radius:30px;text-decoration:none;font-weight:700;font-size:15px}
.sub-form{display:flex;gap:8px;margin-top:14px;flex-wrap:wrap}.sub-form input{flex:1;min-width:200px;padding:13px 14px;border:2px solid #fff;border-radius:30px;font-size:15px;background:#fff}
.sub-form button{background:var(--tang);color:#fff;border:0;border-radius:30px;padding:13px 20px;font-weight:700;cursor:pointer}
.sub-note{font-size:13px;color:var(--muted);margin-top:6px}
main{max-width:1120px;margin:0 auto;padding:16px 16px 40px}
section{margin-top:26px}h2{font-size:32px;margin:0 0 6px;letter-spacing:-.01em}
.sub{color:var(--muted);font-size:15px;margin:0 0 14px}
.top5{background:#fff;border-radius:28px;padding:22px 20px 14px;box-shadow:0 12px 36px rgba(31,26,46,.06)}
.top5 .grid{grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px}.top5 .card{box-shadow:none;border:1px solid #F1E9DE}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:16px}
.card{background:#fff;border-radius:24px;padding:14px;display:flex;flex-direction:column;gap:8px;box-shadow:0 1px 0 #ECE3D7;overflow:hidden;position:relative}
.ph{position:relative;display:block;border-radius:16px;overflow:hidden;background:#fff;border:1px solid #F3EDE4}
.ph img{width:100%;aspect-ratio:1/1;object-fit:contain;display:block;background:#fff}
.ph .stk{position:absolute;top:10px;left:10px}
.price{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;line-height:1}.price b{font-size:32px;font-weight:900;letter-spacing:-.03em;color:var(--tang);font-variant-numeric:tabular-nums}.price s{color:var(--muted);font-size:15px;font-weight:500}.price .off{background:var(--yel);color:var(--ink);font-weight:800;font-size:12px;padding:3px 8px;border-radius:20px}.top5 .price b{font-size:28px}.fact.low{color:var(--green);font-weight:700}
.tier{font-size:32px;font-weight:900;letter-spacing:-.03em;color:var(--ink);line-height:1;font-variant-numeric:tabular-nums;white-space:nowrap}.top5 .tier{font-size:28px}.tier.small{font-size:22px}
.card h3{font-size:17px;line-height:1.3;margin:0;font-weight:600;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.proof{display:flex;gap:8px;flex-wrap:wrap;font-size:12px;align-items:center;min-height:16px}
.chk{background:var(--green);color:#fff;padding:3px 8px;border-radius:20px;font-weight:600;white-space:nowrap}
.fact{color:var(--muted);font-weight:500}.saved:empty{display:none}
.why{font-size:13px;color:var(--muted)}.why.ss{color:var(--ink);font-weight:600}
.code{border:1px dashed var(--tang);background:var(--cream);border-radius:10px;padding:10px;font-size:14px;cursor:pointer;text-align:left}
.code b{letter-spacing:.12em}.code span{float:right;color:var(--muted);font-size:12px}
.go{margin-top:auto;background:var(--tang);color:#fff;text-align:center;padding:14px;border-radius:30px;text-decoration:none;font-weight:700;font-size:16px;white-space:nowrap}.top5 .go{font-size:14px;padding:12px}.go:hover{background:#9A3409}
.paid{font-size:11px;color:var(--muted);text-align:center}.chip{background:var(--lav);color:var(--ink);padding:2px 8px;border-radius:20px}
.cats{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}.cats button,.bar button{border:1px solid #E6DCCF;background:#fff;border-radius:30px;padding:8px 14px;font-size:13px;cursor:pointer;color:var(--ink)}
.cats button.on,.bar button.on{background:#fff;border:2px solid var(--ink);color:var(--ink);font-weight:800}
.bar{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 16px;align-items:center}.bar input,.bar select{padding:10px 12px;border:1px solid #E6DCCF;border-radius:30px;font-size:14px;background:#fff}
.virals{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:12px}
.viral{background:#fff;border-radius:18px;padding:12px;text-decoration:none;color:var(--ink);display:block;border:1px solid #F1E9DE}.viral span{display:block;font-size:11px;color:var(--muted);margin-top:4px}.viral em{display:block;font-style:normal;font-size:13px;font-weight:600;margin-top:4px}
.empty{display:none;padding:24px;text-align:center;color:var(--muted)}
.cats button:nth-of-type(n+9):not(.more){display:none}.cats.open button{display:inline-block}.cats.open .more{display:none}
.tiernav{position:sticky;top:0;z-index:8;background:var(--cream);display:flex;gap:8px;overflow-x:auto;padding:10px 0;margin:6px 0 2px;border-bottom:1px solid #EFE6DA}
.tiernav a{flex:0 0 auto;background:#fff;border:2px solid var(--ink);color:var(--ink);text-decoration:none;font-weight:800;font-size:14px;padding:8px 14px;border-radius:30px}.tiernav a small{font-weight:600;color:var(--muted)}
.tier-sec h2{display:flex;align-items:center;gap:12px}.tier-sec h2 .stk{font-size:11px}.tier-sec{scroll-margin-top:64px}
footer{max-width:1120px;margin:30px auto;padding:0 16px;font-size:12px;color:var(--muted);line-height:1.6}footer a{color:var(--muted)}
.stick{position:fixed;left:50%;transform:translateX(-50%);bottom:14px;background:#fff;color:var(--ink);border:2px solid var(--ink);text-align:center;padding:12px 22px;font-weight:700;z-index:9;text-decoration:none;border-radius:30px;box-shadow:0 8px 24px rgba(31,26,46,.25)}
:focus-visible{outline:3px solid #1f4fd8;outline-offset:2px;scroll-margin-bottom:70px}.skip{position:absolute;left:-999px}.skip:focus{left:8px;top:8px;background:#fff;padding:8px;z-index:20}
.kicker,.rule,.mia,.tested-badge,.badge,.top,.where,.meta,.now,.was,.stars,.amz,.coupon,.asof,.also,.buzz,.hist,.feats{display:none}
@media(max-width:760px){.hero{grid-template-columns:1fr;padding-top:14px}h1{font-size:40px}.hero img.scene{order:-1;max-height:230px;object-fit:cover;object-position:70% 20%}.tier{font-size:30px}.price b{font-size:30px}
.top5 .grid{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;gap:12px;padding-bottom:8px}.top5 .card{min-width:78%;scroll-snap-align:start}}
"""


JS = """
const rtf=new Intl.RelativeTimeFormat('en',{numeric:'auto'});
document.querySelectorAll('.code').forEach(b=>b.onclick=()=>{navigator.clipboard&&navigator.clipboard.writeText(b.dataset.code);b.querySelector('span').textContent='copied!';});
let filt='all',cat='';const q=document.getElementById('q'),st=document.getElementById('store');
function apply(){const s=q.value.trim().toLowerCase(),sv=st.value;let n=0;document.querySelectorAll('.card').forEach(c=>{
 const ok=(filt==='all'||c.classList.contains(filt))&&(!s||c.dataset.title.includes(s))&&(!cat||c.dataset.cat===cat)&&(!sv||c.dataset.store===sv);
 c.style.display=ok?'':'none';if(ok)n++;});document.querySelectorAll('.tier-sec').forEach(sec=>{const any=[...sec.querySelectorAll('.card')].some(c=>c.style.display!=='none');sec.style.display=any?'':'none';});const e=document.getElementById('empty'),k=document.getElementById('count');if(e)e.style.display=n?'none':'block';if(k)k.textContent=n+' deals shown';}
document.querySelectorAll('.cats button').forEach(b=>b.onclick=()=>{document.querySelectorAll('.cats button').forEach(x=>{x.classList.remove('on');x.setAttribute('aria-pressed',x===b);});b.classList.add('on');cat=b.dataset.c;apply();});
st.onchange=apply;q.oninput=apply;
document.querySelectorAll('.bar button').forEach(b=>b.onclick=()=>{document.querySelectorAll('.bar button').forEach(x=>{x.classList.remove('on');x.setAttribute('aria-pressed',x===b);});b.classList.add('on');filt=b.dataset.f;apply();});
/* our own counts: real clicks on our buttons, nothing else. Shown only when >= 5. */
const H='/hit';
document.querySelectorAll('[data-track]').forEach(a=>a.addEventListener('click',()=>{try{navigator.sendBeacon?navigator.sendBeacon(H,new Blob([JSON.stringify({k:a.dataset.track,t:'click'})],{type:'application/json'})):fetch(H,{method:'POST',body:JSON.stringify({k:a.dataset.track,t:'click'}),keepalive:true});}catch(e){}}));
(async()=>{try{const ks=[...new Set([...document.querySelectorAll('.saved[data-saved]')].map(e=>e.dataset.saved))];if(!ks.length)return;
 const r=await fetch(H+'?k='+ks.slice(0,120).join(','));if(!r.ok)return;const j=await r.json();
 document.querySelectorAll('.saved[data-saved]').forEach(e=>{const c=(j[e.dataset.saved]||{}).click||0;if(c>=5)e.textContent=c+' clicks this week';});}catch(e){}})();
const _mc=document.getElementById('morecats');if(_mc)_mc.onclick=()=>document.getElementById('cats').classList.add('open');
const _st=document.querySelector('.stick'),_t5=document.getElementById('top5');if(_st&&_t5&&'IntersectionObserver' in window){new IntersectionObserver(es=>{const r=_t5.getBoundingClientRect();_st.style.display=(r.top<innerHeight*0.6)?'none':'';}).observe(_t5);addEventListener('scroll',()=>{const r=_t5.getBoundingClientRect();_st.style.display=(r.top<innerHeight*0.6)?'none':'';},{passive:true});}
try{if(location.search.includes('admin=1'))localStorage.setItem('mfic-admin','1');if(localStorage.getItem('mfic-admin'))document.body.classList.add('is-admin');}catch(e){}
"""


LEGAL_UPDATED = "November 12, 2026"
LEGAL = {
"disclosure.html": ("Affiliate disclosure", """
<p>Mom Found It Cheaper ("we", "us") shares deals on products sold by other companies. Many links on our website, Facebook group,
videos and other channels are <b>affiliate links</b>. If you click one and buy something, we may earn a small commission from the
retailer or brand. <b>It costs you nothing extra.</b></p>
<p><b>Amazon:</b> As an Amazon Associate I earn from qualifying purchases.</p>
<p>We may also earn from other affiliate programs (for example Walmart, Target, eBay or brand programs) and from brands that pay to
feature a deal. Sponsored or paid posts are always labeled <b>#ad</b> or <b>Sponsored</b>.</p>
<p>Commissions never change the price you pay. We only share deals we think are worth your time, but you should always decide for
yourself whether a product is right for you.</p>"""),
"terms.html": ("Terms &amp; conditions", """
<p>By using this website, our Facebook group or any of our channels, you agree to these terms. If you do not agree, please do not use them.</p>
<h3>1. Information only</h3><p>Everything we share is general shopping information, not professional, financial, medical or safety advice.
Product descriptions, features, prices and ratings come from deal listings and retailers. We try to be accurate but we do not guarantee that
any information is complete, current or correct.</p>
<h3>2. Prices, coupons and codes</h3><p>Prices, stock, coupons and promo codes are set by retailers and can change, sell out or expire at any time,
sometimes within minutes. "Lowest price we've seen"
compares only prices we have recorded. Always check the final price at checkout before you buy.</p>
<h3>3. We are not the seller</h3><p>All purchases are made directly with the retailer. We do not sell products, take payments, ship orders, or handle
returns, refunds, warranties or product safety. Any issue with an order is between you and the retailer or manufacturer.</p>
<h3>4. Third-party sites</h3><p>Our links take you to websites we do not own or control. Their own terms and privacy policies apply. We are not
responsible for their content, products, services or practices.</p>
<h3>5. Affiliate links</h3><p>Some links earn us a commission. See our <a href="disclosure.html">affiliate disclosure</a>.</p>
<h3>6. Community rules</h3><p>In our Facebook group and other channels: be kind; no spam, selling, self-promotion or referral links; no scams,
counterfeit goods or misleading posts. We may remove posts or members at our discretion.</p>
<h3>7. No warranty</h3><p>Our website and channels are provided "as is" and "as available", without warranties of any kind.</p>
<h3>8. Limitation of liability</h3><p>To the fullest extent allowed by law, Mom Found It Cheaper and its owners are not liable for any loss or damage
arising from your use of our content, links or any product or retailer, including expired deals, price changes, or product problems.</p>
<h3>9. Trademarks</h3><p>Amazon and all other store and brand names are trademarks of their owners. We are not affiliated with or endorsed by them
unless we say so.</p>
<h3>10. Changes</h3><p>We may update these terms at any time. The date below shows the latest version.</p>
<h3>11. Governing law</h3><p>These terms are governed by the laws of the State of Florida, USA.</p>"""),
"privacy.html": ("Privacy policy", """
<p>We respect your privacy. This website does not ask you to create an account and does not collect your name, email or payment details.</p>
<h3>What is collected</h3><p>Our hosting provider (Cloudflare) may record basic technical information such as your IP address, browser and
pages visited, for security and performance. Fonts are loaded from Google Fonts, which may receive your IP address. Your browser may store
a small preference (for example, filters you used) on your own device.</p>
<h3>Affiliate partners</h3><p>When you click a link to a retailer such as Amazon, that retailer may use cookies to track the visit and any
purchase so we can be credited. Their privacy policies apply once you leave our site.</p>
<h3>Facebook group</h3><p>If you join our Facebook group, Facebook's own privacy policy applies to what you share there.</p>
<h3>Children</h3><p>Our content is meant for adults and is not directed at children under 13.</p>
<h3>Contact</h3><p>Questions? Message us through our Facebook group.</p>"""),
}


def legal_page(title, body):
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} | {BRAND}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800;900&family=Playfair+Display:wght@700&display=swap" rel="stylesheet">
<style>{CSS} main{{max-width:760px}} main p,main li{{line-height:1.65;font-size:15px}} main h3{{font-family:'Playfair Display',Georgia,serif;margin:22px 0 6px}}</style></head>
<body><header><div class="kicker"><a href="index.html" style="color:inherit;text-decoration:none">&larr; MOM FOUND IT CHEAPER</a></div><h1>{title}</h1></header>
<main>{body}<p style="color:#7a7068;font-size:13px">Last updated {LEGAL_UPDATED}.</p></main></body></html>"""


def seasonal_sections(deals, history, tested, today=None):
    """One curated block per upcoming shopping moment (see seasonal.py)."""
    from seasonal import active, matches
    out = []
    for ev in [e for e in active(today) if e["key"] in ("thanksgiving", "stocking", "football")][:3]:
        ms = [d for d in matches(deals, ev) if not d.get("expired") and d.get("asin") and is_amazon(d)
              and thumb_for(d) and savings(d)[1] >= 10]
        ms.sort(key=lambda d: (bool(d.get("asin")), d.get("thumbs", 0)), reverse=True)
        if not ms:
            continue
        when = "today" if ev["days"] == 0 else f"in {ev['days']} days" if ev["days"] > 1 else "tomorrow"
        cards = "".join(card(d, history, tested) for d in ms[:12])
        out.append(f'<section class="season"><h2>{html.escape(ev["theme"])}</h2>'
                   f'<p class="sub">{html.escape(ev["name"])} is {when}. Hand-picked matches from today\'s deals.</p>'
                   f'<div class="grid">{cards}</div></section>')
    return "".join(out)


NEWSLETTER_ACTION = os.environ.get("NEWSLETTER_ACTION", "").strip()   # e.g. https://buttondown.com/api/emails/embed-subscribe/momfounditcheaper


def _latest_meta():
    """Most recently checked product meta (for the hero proof line)."""
    best = {}
    for m in META.values():
        if isinstance(m, dict) and m.get("checked", 0) > best.get("checked", 0):
            best = m
    return best


def hero_hook():
    from datetime import date
    d = date.today()
    if date(d.year, 11, 20) <= d <= date(d.year, 12, 2):
        return "Black Friday,<br><em>checked.</em>"
    if date(d.year, 12, 3) <= d <= date(d.year, 12, 24):
        return "Gifts under $25,<br><em>checked.</em>"
    return "Real deals,<br><em>checked daily.</em>"


def hero_sticker():
    from datetime import date
    d = date.today()
    return "BF WEEK" if date(d.year, 11, 20) <= d <= date(d.year, 12, 2) else "NEW EVERY MORNING"


def signup_html():
    """Email capture. Shows a live form once NEWSLETTER_ACTION is set (Buttondown/Beehiiv/Mailchimp embed URL);
    until then a Facebook-follow prompt so the slot is never empty."""
    if NEWSLETTER_ACTION:
        return (f'<form class="sub-form" action="{html.escape(NEWSLETTER_ACTION)}" method="post" target="_blank">'
                '<label class="skip" for="em">Email</label><input id="em" type="email" name="email" required placeholder="your@email.com" autocomplete="email">'
                '<button type="submit">Send me the Top 5 at 7am</button></form>'
                '<div class="sub-note">Free. One email a day, unsubscribe any time. No spam, ever.</div>')
    return '<div class="sub-note">Daily Top 5 email is coming. Until then, <a href="https://www.facebook.com/groups/1815840112666601" target="_blank" rel="noopener">follow us on Facebook</a> so you don\'t miss a find.</div>'


def top5(picked, history, tested):
    """Today's Top 5: verified cards only, ranked by votes, buzz, freshness. Big-ticket/non-mom items skipped."""
    import re as _re
    skip = _re.compile(r"gaming pc|desktop|rtx|blu-ray|4k uhd|vinyl|motherboard|cpu|ssd|server", _re.I)
    def rank(d):
        return (d.get("thumbs", 0), len(viral_sources(d, SIGNALS)), d["seen"])
    mom = {"Toys & Games": 3, "Baby & Kids": 3, "Home & Kitchen": 3, "Beauty & Health": 2, "Holiday & Seasonal": 2,
           "Grocery & Household": 2, "Pets": 2, "Fashion": 1, "Office & School": 1, "Sports & Fitness": 1}
    def rank(d):
        return (mom.get(d.get("category", ""), 0), d.get("thumbs", 0), len(viral_sources(d, SIGNALS)), d["seen"])
    pool = [d for d in picked if not skip.search(d["title"])]
    best = sorted(pool, key=rank, reverse=True)[:5]
    if len(best) < 3:
        return ""
    cards = "".join(card(d, history, tested, rank=i, idsuffix="-t5") for i, d in enumerate(best, 1))
    return (f'<section class="top5" id="top5"><h2>Today\'s Top 5</h2>'
            f'<p class="sub">Five I\'d buy today. Each link checked against Amazon in the last 24 hours.</p>'
            f'<div class="grid">{cards}</div></section>')


TIERS = [("under-10", "Under $10", 0, 10), ("under-20", "Under $20", 10, 20), ("under-25", "Under $25", 20, 25),
         ("under-50", "Under $50", 25, 50), ("under-100", "Under $100", 50, 100), ("over-100", "$100 and up", 100, 10**9)]


def _amazon_now(d):
    m = META.get(d.get("asin", "")) or {}
    return price_num(m.get("now")) if m.get("v", 0) >= 4 else None


_NO_SITE = re.compile(r"\b(?:knife|knives|pocketknife|blade|multi-?tool|machete|hatchet|axe|airsoft|bb gun|pellet gun)\b", re.I)


def tier_sections(picked, history, tested):
    """The main body: every verified deal filed under ONE price tier (Amazon's checked price), cheapest tier first.
    Cards inside a tier are sorted by mom-relevance then votes. A sticky tier nav jumps between them."""
    mom = {"Toys & Games": 3, "Baby & Kids": 3, "Home & Kitchen": 3, "Beauty & Health": 2, "Holiday & Seasonal": 2,
           "Grocery & Household": 2, "Pets": 2, "Fashion": 1, "Office & School": 1, "Sports & Fitness": 1}
    buckets = {k: [] for k, *_ in TIERS}
    for d in picked:
        p = _amazon_now(d)
        if p is None:
            continue
        for key, _, lo, hi in TIERS:
            if lo <= p < hi:
                buckets[key].append(d)
                break
    nav, out = [], []
    for key, label, lo, hi in TIERS:
        items = sorted(buckets[key], key=lambda d: (mom.get(d.get("category", ""), 0), d.get("thumbs", 0), d["seen"]), reverse=True)
        if not items:
            continue
        nav.append(f'<a href="#{key}">{html.escape(label)} <small>{len(items)}</small></a>')
        cards = "".join(card(d, history, tested, idsuffix="-" + key, in_tier=True) for d in items)
        out.append(f'<section class="tier-sec" id="{key}"><h2>{html.escape(label)} <span class="stk">{len(items)} DEALS</span></h2>'
                   f'<p class="sub">Checked against Amazon in the last 24 hours. Prices move; tap for the live price.</p>'
                   f'<div class="grid">{cards}</div></section>')
    return f'<nav class="tiernav" aria-label="Price tiers">{"".join(nav)}</nav>' + "".join(out)


def posts_gallery():
    imgs = sorted(Path("webposts").glob("post_*.png"))
    if not imgs or AMAZON_PRICES == "hide":      # post images carry Amazon photos
        return ""
    if not imgs:
        return ""
    OUT.mkdir(exist_ok=True)
    (OUT / "posts").mkdir(exist_ok=True)
    tiles = []
    for p in imgs:
        (OUT / "posts" / p.name).write_bytes(p.read_bytes())
        tiles.append(f'<a href="posts/{p.name}" target="_blank" rel="noopener"><img src="posts/{p.name}" loading="lazy" alt="Today\'s deal post {p.stem.split(chr(95))[-1]}"></a>')
    return ('<section><h2>Today\'s posts</h2><p class="sub">The same posts we share in the Facebook group. Tap one to see it full size.</p>'
            f'<div class="gallery">{"".join(tiles)}</div></section>')


try:
    BLOCK = set(json.loads(Path("data/blocklist.json").read_text()).get("asins", []))
except Exception:
    BLOCK = set()


def main():
    from deal_finder import category_of, store_of
    deals = load("deals.json", [])
    for d in deals:                      # older saved deals: tag them now
        d["category"] = category_of((_amz_title(d) + " " + d["title"]).strip())   # always recompute: keywords improve, saved tags go stale
        d.setdefault("store", store_of(d["title"] + " " + d.get("desc", "")))
    history = load("price_history.json", {})
    viral = load("viral.json", {})
    tested = load("tested.json", {})
    now = datetime.now(timezone.utc).strftime("%b %d, %Y %H:%M UTC")
    # tested deals first, then deals with codes, then newest
    def rank(d):
        i = deal_id(d)
        return (1 if i in tested else 0, len(viral_sources(d, SIGNALS)),
                1 if d.get("code") and d["code"] != "w/ code" else 0, d["seen"])
    PER_CATEGORY = 100
    count, picked, seen_asin = {}, [], set()
    for d in sorted(deals, key=rank, reverse=True):
        c = d.get("category", "Everything else")
        _t = tested.get(deal_id(d))
        if is_amazon(d) and not d.get("asin") and not (isinstance(_t, dict) and _t.get("asin")):
            continue                  # Amazon deal with no ASIN = no affiliate link; skip
        if not thumb_for(d) or not link_verified(d):
            continue                  # site shows only deals with a real product photo
        if d.get("asin") in BLOCK:
            continue                  # owner/QA blocklist (wrong variant etc.)
        if _NO_SITE.search(d["title"]) or _NO_SITE.search(str((META.get(d.get("asin", "")) or {}).get("title", ""))):
            continue                  # no knives/weapons on a mom site (owner rule)
        if d.get("asin"):
            if d["asin"] in seen_asin:
                continue              # one card per product
            seen_asin.add(d["asin"])
        if count.get(c, 0) < PER_CATEGORY:
            count[c] = count.get(c, 0) + 1
            picked.append(d)
    cats = sorted(count, key=lambda c: (c == "Everything else", -count[c]))
    stores = sorted({d.get("store", "Other") for d in picked}, key=lambda s: (s == "Other", s))
    cat_buttons = "".join(f'<button data-c="{html.escape(c)}">{html.escape(c)} <small>{count[c]}</small></button>' for c in cats)
    store_opts = "".join(f'<option>{html.escape(s)}</option>' for s in stores)
    cards = "".join(card(d, history, tested) for d in picked)
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{BRAND} | Daily Amazon Deals for Moms, Checked Every Morning</title>
<link rel="canonical" href="https://momfounditcheaper.com/">
<meta property="og:title" content="Mom Found It Cheaper | Daily Deals">
<meta property="og:url" content="https://momfounditcheaper.com/">
<meta property="og:type" content="website">
<meta property="og:description" content="Daily deals, viral finds and price drops, checked against Amazon.">
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<meta name="description" content="A Tampa mom's daily finds: viral and proven products, promo codes, coupons and price drops in one place.">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Playfair+Display:ital,wght@0,600;0,700;1,400&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body>
<a class="skip" href="#todays">Skip to today's deals</a>
<header><div class="hero"><div class="hero-txt"><div class="wordmark">Mom Found It Cheaper</div>
<span class="stk hero-stk">{hero_sticker()}</span>
<h1>{hero_hook()}</h1>
<p class="proofline">&#10003; Every link checked against Amazon in the last 24 hours{(' &middot; ' + _checked_label(_latest_meta()).replace('Checked ', '')) if _latest_meta().get('checked') else ''}. I'm Mia. Tap any card for today's Amazon price.</p>
{signup_html()}
<a class="join" href="#top5">See today's 5 &darr;</a></div>
<img class="scene" src="mia-scene.jpg" width="1428" height="803" alt="Mia, the mom behind Mom Found It Cheaper, holding a stack of checked delivery boxes" fetchpriority="high"></div></header>
<main>
<p class="sub" style="padding:0 16px"><b>As an Amazon Associate I earn from qualifying purchases.</b> Buttons below are paid affiliate links (#ad).</p>
{top5(picked, history, tested)}
{posts_gallery()}
{seasonal_sections(picked, history, tested)}
{viral_section(viral)}
<section id="todays"><h2>All of today's deals, by price</h2><p class="sub">{len(picked)} verified deals. Pick a price, or filter by category.</p>
<div class="cats" id="cats"><button class="on" data-c="">All categories</button>{cat_buttons}<button type="button" class="more" id="morecats">More…</button></div>
<div class="bar"><input id="q" placeholder="Search deals…" aria-label="Search deals"><select id="store" aria-label="Filter by store" style="display:none"><option value="">All stores</option>{store_opts}</select>
<button class="on" data-f="all">All</button>{'<button data-f="has-code">Codes</button>' if 'has-code' in cards else ''}{'<button data-f="has-coupon">Coupons</button>' if 'has-coupon' in cards else ''}<button data-f="viral">Trending</button></div>
<div id="empty" class="empty" role="status">No deals match this filter right now. Try another category or clear the search.</div><div id="count" class="sub" aria-live="polite" role="status"></div>
</section>
{tier_sections(picked, history, tested)}
</main>
<footer><b>Affiliate disclosure:</b> As an Amazon Associate I earn from qualifying purchases. Some links are affiliate links (#ad) — if you buy through them we may earn a commission at no extra cost to you.<br>
Prices, availability, coupons and promo codes are set by the retailers and can change or expire at any time. Always check the final price at checkout before you buy.
We are not the seller and do not handle orders, shipping, returns or warranties — contact the retailer for those.
"Lowest price we've seen" is based only on prices we have recorded, not a guarantee of an all-time low. Product details come from the deal listing and the retailer; we do not guarantee them.<br>
Deals are found from public deal feeds and checked against Amazon each morning. Amazon and other store names are trademarks of their owners; we are not affiliated with or endorsed by them.<br>
<a href="disclosure.html">Affiliate disclosure</a> · <a href="terms.html">Terms &amp; conditions</a> · <a href="privacy.html">Privacy policy</a></footer>
<a class="stick" href="#top5">Today's 5 &darr;</a>
<script>{JS}</script>{DEEPLINK_JS}</body></html>"""
    page = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", page)      # no zero-width characters anywhere on the page
    OUT.mkdir(exist_ok=True)
    (OUT / "index.html").write_text(page)
    import shutil
    if Path("brand/mia_avatar_circle_240.png").exists():
        shutil.copy("brand/mia_avatar_circle_240.png", OUT / "mia.png")
    for pd in sorted(Path("pins").glob("*/"))[-2:]:          # latest pin batches, public for QA tools and bulk upload
        dst = OUT / "pins" / pd.name
        dst.mkdir(parents=True, exist_ok=True)
        for f in pd.iterdir():
            shutil.copy(f, dst / f.name)
    if Path("queue/QUEUE.md").exists():
        shutil.copy("queue/QUEUE.md", OUT / "queue.md")
    for src in ("queue", "control", "status"):            # machine-readable feeds for the Control Center dashboard + n8n
        sp = Path(src)
        if sp.is_dir():
            dd = OUT / src
            dd.mkdir(parents=True, exist_ok=True)
            for f in sp.glob("*.json"):
                shutil.copy(f, dd / f.name)
    if Path("brand/mia_hero_scene.jpg").exists():          # pre-saved JPEG: Cloudflare's build has no PIL
        shutil.copy("brand/mia_hero_scene.jpg", OUT / "mia-scene.jpg")
    (OUT / "favicon.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#B84300"/><text x="32" y="44" font-size="34" font-weight="700" text-anchor="middle" fill="#fff" font-family="Arial">M</text></svg>')
    (OUT / "robots.txt").write_text("User-agent: *\nAllow: /\nDisallow: /review\nSitemap: https://momfounditcheaper.com/sitemap.xml\n")
    try:                                   # unlisted review page of today's queue (Cloudflare build runs this file only)
        import make_review
        make_review.main()
    except Exception as _e:
        print("review page skipped:", _e)
    (OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(f"<url><loc>https://momfounditcheaper.com/{u}</loc></url>" for u in ("", "disclosure.html", "privacy.html", "terms.html")) + "</urlset>\n")
    (OUT / "404.html").write_text(legal_page("Page not found", "<p>That page does not exist. <a href=\"/\">Back to today&rsquo;s deals</a>.</p>"))
    for name, (title, body) in LEGAL.items():
        (OUT / name).write_text(legal_page(title, body))
    (OUT / ".nojekyll").write_text("")
    print(f"site built: {len(deals)} deals, {len(viral.get('videos', []))} viral, {len(tested)} tested")


if __name__ == "__main__":
    main()
