"""One shared product-name + price check. Used by build_site.py (site gate), amazon_local.py (daily report)
and anything else that links a deal to an Amazon page. A link is OK only when the live Amazon title matches the
deal title AND the deal price is within TOL of the Amazon price."""
import html
import json
import re
from pathlib import Path

TOL = 0.12
STOP = set("the a an and of for with in on to by amazon only just from new black friday shipped women men womens mens kids pack pc set".split())
ARTICLE = re.compile(r"\b(best amazon|deals you can|peek at|collection of|sale is live|roundup|amazon deals? (?:today|of the day)|"
                     r"rare black friday|everything we|things we|you can still|you need to|10 random|11 best|\d+ best)\b", re.I)


def words(s):
    return {w for w in re.findall(r"[a-z0-9]+", re.sub(r"&#?\w+;", "", html.unescape(s or "")).lower())
            if w not in STOP and len(w) > 2}


def num(s):
    m = re.search(r"[\d,]+(?:\.\d+)?", s or "")
    return float(m.group(0).replace(",", "")) if m else None


def title_score(card_title, amazon_title):
    A, B = words(card_title), words(amazon_title)
    return max(len(A & B) / max(1, len(B)), len(A & B) / max(1, len(A)))


def check(card_title, card_price, amazon_title, amazon_now):
    """Return (ok, reason)."""
    if not amazon_title:
        return False, "no Amazon title read"
    if ARTICLE.search(card_title or ""):
        return False, "deal title looks like an article, not a product"
    s = title_score(card_title, amazon_title)
    if s < 0.5:
        return False, f"name mismatch ({s:.1f})"
    cp, pp = num(card_price), num(amazon_now)
    if not cp or not pp:
        return False, "price missing"
    if abs(cp - pp) / pp > TOL:
        return False, f"price card {card_price} vs Amazon {amazon_now}"
    return True, "ok"


def amazon_side(asin, meta, lc):
    """Best available live Amazon title/price: Lenovo meta (v4, fresh) else the browser spot check."""
    m = meta.get(asin) or {}
    if m.get("v", 0) >= 4 and m.get("checked") and m.get("title") and m.get("now"):
        return m["title"], m["now"]
    x = (lc or {}).get(asin)
    return (x["title32"], x["now"]) if x else (None, None)


def report(deals, meta, lc, out="data/link_report.json"):
    rows = {}
    for d in deals:
        a = d.get("asin")
        if not a:
            continue
        t, p = amazon_side(a, meta, lc)
        ok, why = check(d.get("title", ""), d.get("price", ""), t, p)
        rows[d["id"]] = {"asin": a, "ok": ok, "why": why}
    Path(out).write_text(json.dumps(rows, indent=0))
    return rows
