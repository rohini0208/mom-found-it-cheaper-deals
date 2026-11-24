"""Run on YOUR home computer. Drives your real Chrome (needs: pip install playwright), so Amazon treats it like you browsing.
Fetches Amazon product photo + rating + review count + list price for deals that lack them,
saves into photos/ and data/product_meta.json, then pushes to GitHub. No Claude, no tokens.
Temporary until the Amazon Creators API is available. Slow and polite on purpose (3-6 s apart, max 100/run).
Setup: see SETUP_LENOVO.md.   Run:  python amazon_local.py
"""
import json
import random
import re
import subprocess
import sys
import time
from pathlib import Path

MAX_RUN = 250
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")
H = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9", "Accept": "text/html,application/xhtml+xml"}
PH, META = Path("photos"), Path("data/product_meta.json")


def sh(*a):
    return subprocess.run(a, capture_output=True, text=True)


GIT = ["git", "-c", "user.name=photo-bot", "-c", "user.email=photo-bot@users.noreply.github.com"]


def parse_reviews(t):
    t = t.replace(",", "")
    return int(float(t[:-1]) * 1000) if t[-1:] in "Kk" else int(float(t))


ASIN_MAP = Path("data/asin_map.json")
ASIN_PAT = re.compile(r"(?:/dp/|/gp/product/|/gp/aw/d/|asin=)([A-Z0-9]{10})(?:[/?&\"' ]|$)")


def resolve_asins(ctx, deals, limit=150):
    """Most Amazon deals from the feeds carry no product ID (only ~1 in 5 do). Open each deal page in your
    Chrome, read the Amazon link behind 'Get Deal' and save deal id -> ASIN. deal_finder.py applies the map."""
    amap = json.loads(ASIN_MAP.read_text()) if ASIN_MAP.exists() else {}
    todo = [d for d in sorted(deals, key=lambda x: x.get("thumbs", 0), reverse=True)
            if not d.get("asin") and d.get("store") == "Amazon" and not d.get("expired") and not amap.get(d["id"])
            and str(d["id"]).startswith("http")][:limit]
    pg = ctx.new_page()
    got = 0
    for d in todo:
        try:
            pg.goto(d["id"], wait_until="domcontentloaded", timeout=40000)
            pg.wait_for_timeout(1500)
            html = pg.content().replace("%2F", "/")
            hrefs = pg.evaluate("() => [...document.querySelectorAll('a[href*=\"amazon.com\"], a[href*=\"amzn.to\"], a[data-href*=\"amazon\"]')].map(a => a.href || a.dataset.href)")
            hit = pg.evaluate("() => { const e = document.querySelector('[data-aps-asin]'); return e ? e.dataset.apsAsin : null; }")
            if hit and not re.fullmatch(r"[A-Z0-9]{10}", hit):
                hit = None
            for h in ([] if hit else list(hrefs or []) + [html]):
                m = ASIN_PAT.search(h or "")
                if m:
                    hit = m.group(1)
                    break
            amap[d["id"]] = hit or ""            # empty = looked, none found (do not retry forever)
            got += bool(hit)
        except Exception as e:
            print("asin lookup failed:", str(e)[:80])
    pg.close()
    ASIN_MAP.write_text(json.dumps(amap, indent=0))
    print(f"asin map: +{got} of {len(todo)} looked up")


def stale(meta, a):
    """Re-check a product when new fields are missing or the data is older than 20 hours."""
    m = meta.get(a)
    if not m or m.get("v") != 4 or not (PH / f"{a}.jpg").exists():
        return True
    return time.time() - m.get("checked", 0) > 20 * 3600


PROMO_JS = """() => {
    const t = (sel) => { const e = document.querySelector(sel); return e ? e.innerText.replace(/\\s+/g, ' ').trim() : ''; };
    const root = document.querySelector('#ppd') || document.body;
    const promo = [...root.querySelectorAll('#promoPriceBlockMessage_feature_div, #couponFeature, [id^=couponText], [id^=promoMessage], .promoPriceBlockMessage, #applicable_promotion_list_sec, #vpcButton, #couponBadgeRegularVpc')]
        .map(e => e.innerText.replace(/\\s+/g, ' ').trim()).filter(Boolean).join(' | ').slice(0, 500);
    return {promo: promo,
            color: t('#variation_color_name .selection'), size: t('#variation_size_name .selection'),
            style: t('#variation_style_name .selection'),
            avail: t('#availability'), title: t('#productTitle'), seller: t('#merchant-info').slice(0, 120)}; }"""


def main():
    from playwright.sync_api import sync_playwright
    sh(*GIT, "pull", "--rebase", "-q")
    deals = json.loads(Path("data/deals.json").read_text())
    meta = json.loads(META.read_text()) if META.exists() else {}
    PH.mkdir(exist_ok=True)
    todo, seen = [], set()
    for d in sorted(deals, key=lambda x: x.get("thumbs", 0), reverse=True):   # best deals first
        a = d.get("asin", "")
        if a and a not in seen and not d.get("expired") and stale(meta, a):
            seen.add(a)
            todo.append(a)
    for _f in ("data/trends.json", "data/trends_amazon.json"):          # trending tiles need photos too
        try:
            for _s in json.loads(Path(_f).read_text()).get("signals", []):
                _a = _s.get("asin", "")
                if _a and _a not in seen and stale(meta, _a):
                    seen.add(_a)
                    todo.insert(0, _a)
        except Exception:
            pass
    done = 0
    dbg = 0
    amap0 = json.loads(ASIN_MAP.read_text()) if ASIN_MAP.exists() else {}
    with sync_playwright() as p:
        # your real Chrome, with its own saved profile folder (cookies stay between runs)
        ctx = p.chromium.launch_persistent_context(str(Path.home() / ".mfic_chrome"), channel="chrome",
                                                   headless=False, viewport={"width": 1200, "height": 800})
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            resolve_asins(ctx, deals)
        except Exception as e:
            print("asin resolver skipped:", str(e)[:100])
        amap0 = json.loads(ASIN_MAP.read_text()) if ASIN_MAP.exists() else {}
        for d in sorted(deals, key=lambda x: x.get("thumbs", 0), reverse=True):   # use freshly found IDs right away
            a = d.get("asin") or amap0.get(d["id"], "")
            if a and a not in seen and not d.get("expired") and stale(meta, a):
                seen.add(a)
                todo.append(a)
        for a in todo[:MAX_RUN]:
            try:
                page.goto(f"https://www.amazon.com/dp/{a}", wait_until="domcontentloaded", timeout=45000)
                html = page.content()
                if re.search(r"captcha|robot check", html, re.I) and "landingImage" not in html:
                    print("Amazon wants a captcha. Solve it in the Chrome window (you have 90 seconds)...")
                    try:
                        page.wait_for_selector("#landingImage, #imgTagWrapperId", timeout=90000)
                        html = page.content()
                    except Exception:
                        print("captcha not solved, stopping (try again later)")
                        break
                rt = re.search(r'([\d.]+) out of 5 stars', html)
                rc = re.search(r'id="acrCustomerReviewText"[^>]*>\(?([\d,KkMm.]+)', html)
                lp = page.evaluate("""() => {
                    const root = document.querySelector('#ppd') || document.querySelector('#centerCol') || document;
                    const el = root.querySelector('.basisPrice .a-offscreen, [data-a-strike="true"] .a-offscreen, .a-price.a-text-price .a-offscreen');
                    return el ? el.textContent : null; }""")
                lp = re.search(r"\$[\d,.]+", lp or "")
                now = page.evaluate("""() => {
                    const root = document.querySelector('#ppd') || document;
                    const el = root.querySelector('.priceToPay .a-offscreen, #corePrice_feature_div .a-price:not(.a-text-price) .a-offscreen, .a-price:not(.a-text-price) .a-offscreen');
                    return el ? el.textContent : null; }""")
                now = re.search(r"\$[\d,.]+", now or "")
                if not lp:                                  # fallback: "List Price: $X" / "Typical price: $X" text
                    try:
                        txt = page.inner_text("#ppd", timeout=5000)
                    except Exception:
                        txt = ""
                    lp = re.search(r"(?:List Price|Typical price|Was|M\.?S\.?R\.?P\.?)[:\s]*(\$[\d,.]+)", txt)
                    if lp:
                        lp = re.match(r"\$[\d,.]+", lp.group(1))
                if not lp and dbg < 4:                      # still nothing: keep the price section so it can be fixed
                    dbg += 1
                    Path("data/price_debug").mkdir(parents=True, exist_ok=True)
                    try:
                        Path(f"data/price_debug/{a}.txt").write_text(page.inner_text("#ppd", timeout=5000)[:3000])
                    except Exception:
                        pass
                m = re.search(r'"hiRes":"(https:[^"]+)"', html)
                meta[a] = {"rating": float(rt.group(1)) if rt else None,
                           "reviews": parse_reviews(rc.group(1)) if rc else None,
                           "list": lp.group(0) if lp else None, "now": now.group(0) if now else None, "v": 4,
                           "checked": int(time.time())}
                try:                                    # coupons, promo codes, chosen variant, stock
                    meta[a].update(page.evaluate(PROMO_JS))
                except Exception:
                    pass
                if m:
                    img = ctx.request.get(re.sub(r"\._[^.]*_\.", "._SL600_.", m.group(1)))
                    (PH / f"{a}.jpg").write_bytes(img.body())
                done += 1
                print("ok", a, meta[a])
            except Exception as e:
                print("fail", a, str(e)[:100])
            time.sleep(random.uniform(3, 6))
        try:
            sigs = []
            for label, url in (("Amazon Movers & Shakers", "https://www.amazon.com/gp/movers-and-shakers"),
                               ("Amazon Best Sellers", "https://www.amazon.com/Best-Sellers/zgbs")):
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                items = page.evaluate("""() => [...document.querySelectorAll('a[href*="/dp/"]')].map(a => {
                    const m = a.href.match(/\\/dp\\/([A-Z0-9]{10})/); const t = (a.innerText || a.querySelector('img')?.alt || '').trim();
                    return m && t.length > 15 ? [m[1], t.slice(0, 120)] : null; }).filter(Boolean)""")
                seen_a = set()
                for asin, title in items:
                    if asin not in seen_a:
                        seen_a.add(asin)
                        sigs.append({"source": label, "title": title, "link": f"https://www.amazon.com/dp/{asin}",
                                     "asin": asin, "rank": len(seen_a)})
            Path("data/trends_amazon.json").write_text(json.dumps({"signals": sigs[:150]}, indent=1))
            print("amazon trend items:", len(sigs))
        except Exception as e:
            print("amazon trends skipped:", str(e)[:100])
        ctx.close()
    META.write_text(json.dumps(meta, indent=1))
    try:                                                    # trends from the home computer (cloud is blocked)
        import trends_finder
        trends_finder.main()
    except Exception as e:
        print("trends skipped:", str(e)[:100])
    sh(*GIT, "add", "data/trends.json", "data/trends_amazon.json", "photos", "data/product_meta.json", "data/price_debug", "data/asin_map.json")
    if sh(*GIT, "diff", "--cached", "--quiet").returncode:
        sh(*GIT, "commit", "-qm", f"Amazon photos and ratings ({done} products, from home computer)")
        sh(*GIT, "pull", "--rebase", "-q")
        r = sh(*GIT, "push", "-q")
        print("pushed" if r.returncode == 0 else r.stderr)
    print(f"{done} products done, {len(todo) - done} still waiting")


if __name__ == "__main__":
    sys.exit(main())
