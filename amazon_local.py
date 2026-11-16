"""Run on YOUR home computer (home internet address, so Amazon does not show the cloud captcha).
Fetches Amazon product photo + rating + review count + list price for deals that lack them,
saves into photos/ and data/product_meta.json, then pushes to GitHub. No Claude, no tokens.
Temporary until the Amazon Creators API is available. Slow and polite on purpose (3-6 s apart, max 25/run).
Setup: see SETUP_LENOVO.md.   Run:  python amazon_local.py
"""
import json
import random
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

MAX_RUN = 25
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")
H = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9", "Accept": "text/html,application/xhtml+xml"}
PH, META = Path("photos"), Path("data/product_meta.json")


def get(url, binary=False):
    r = urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=30).read()
    return r if binary else r.decode("utf8", "ignore")


def sh(*a):
    return subprocess.run(a, capture_output=True, text=True)


def main():
    sh("git", "pull", "--rebase", "-q")
    deals = json.loads(Path("data/deals.json").read_text())
    meta = json.loads(META.read_text()) if META.exists() else {}
    PH.mkdir(exist_ok=True)
    todo, seen = [], set()
    for d in sorted(deals, key=lambda x: x.get("thumbs", 0), reverse=True):   # best deals first
        a = d.get("asin", "")
        if a and a not in seen and not d.get("expired") and (a not in meta or not (PH / f"{a}.jpg").exists()):
            seen.add(a)
            todo.append(a)
    done = 0
    for a in todo[:MAX_RUN]:
        try:
            page = get(f"https://www.amazon.com/dp/{a}")
            if re.search(r"captcha|robot check", page, re.I) and "landingImage" not in page:
                print("captcha, stopping (try again later)")
                break
            rt = re.search(r'([\d.]+) out of 5 stars', page)
            rc = re.search(r'id="acrCustomerReviewText"[^>]*>\(?([\d,KkMm.]+)', page)
            lp = re.search(r'(?:basisPrice|a-text-price)[^$]{0,400}(\$[\d,.]+)', page)
            m = re.search(r'"hiRes":"(https:[^"]+)"', page)
            reviews = None
            if rc:
                t = rc.group(1).replace(",", "")
                reviews = int(float(t[:-1]) * 1000) if t[-1:] in "Kk" else int(float(t))
            meta[a] = {"rating": float(rt.group(1)) if rt else None, "reviews": reviews,
                       "list": lp.group(1) if lp else None}
            if m:
                (PH / f"{a}.jpg").write_bytes(get(re.sub(r"\._[^.]*_\.", "._SL600_.", m.group(1)), True))
            done += 1
            print("ok", a, meta[a])
        except Exception as e:
            print("fail", a, e)
        time.sleep(random.uniform(3, 6))
    META.write_text(json.dumps(meta, indent=1))
    sh("git", "add", "photos", "data/product_meta.json")
    if sh("git", "diff", "--cached", "--quiet").returncode:
        sh("git", "commit", "-qm", f"Amazon photos and ratings ({done} products, from home computer)")
        print(sh("git", "pull", "--rebase", "-q").stderr, sh("git", "push", "-q").stderr)
    print(f"{done} products done, {len(todo) - done} still waiting")


if __name__ == "__main__":
    sys.exit(main())
