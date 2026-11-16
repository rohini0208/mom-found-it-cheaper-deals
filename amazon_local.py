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

MAX_RUN = 100
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


def main():
    from playwright.sync_api import sync_playwright
    sh(*GIT, "pull", "--rebase", "-q")
    deals = json.loads(Path("data/deals.json").read_text())
    meta = json.loads(META.read_text()) if META.exists() else {}
    PH.mkdir(exist_ok=True)
    todo, seen = [], set()
    for d in sorted(deals, key=lambda x: x.get("thumbs", 0), reverse=True):   # best deals first
        a = d.get("asin", "")
        if a and a not in seen and not d.get("expired") and (a not in meta or meta[a].get("v") != 3 or not (PH / f"{a}.jpg").exists()):
            seen.add(a)
            todo.append(a)
    done = 0
    dbg = 0
    with sync_playwright() as p:
        # your real Chrome, with its own saved profile folder (cookies stay between runs)
        ctx = p.chromium.launch_persistent_context(str(Path.home() / ".mfic_chrome"), channel="chrome",
                                                   headless=False, viewport={"width": 1200, "height": 800})
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
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
                           "list": lp.group(0) if lp else None, "now": now.group(0) if now else None, "v": 3}
                if m:
                    img = ctx.request.get(re.sub(r"\._[^.]*_\.", "._SL600_.", m.group(1)))
                    (PH / f"{a}.jpg").write_bytes(img.body())
                done += 1
                print("ok", a, meta[a])
            except Exception as e:
                print("fail", a, str(e)[:100])
            time.sleep(random.uniform(3, 6))
        ctx.close()
    META.write_text(json.dumps(meta, indent=1))
    sh(*GIT, "add", "photos", "data/product_meta.json", "data/price_debug")
    if sh(*GIT, "diff", "--cached", "--quiet").returncode:
        sh(*GIT, "commit", "-qm", f"Amazon photos and ratings ({done} products, from home computer)")
        sh(*GIT, "pull", "--rebase", "-q")
        r = sh(*GIT, "push", "-q")
        print("pushed" if r.returncode == 0 else r.stderr)
    print(f"{done} products done, {len(todo) - done} still waiting")


if __name__ == "__main__":
    sys.exit(main())
