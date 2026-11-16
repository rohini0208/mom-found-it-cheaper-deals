"""Auto product photos (no browser, no tokens). The deal feeds already carry a product thumbnail;
save it as photos/<ASIN>.jpg for Amazon deals that have no photo yet. Temporary: retire once the
Amazon Creators API (official product images) is available.
Run after deal_finder.py:  python fetch_images.py
"""
import json
import re
import urllib.request
from pathlib import Path

from PIL import Image
import io

PHOTOS = Path("photos")
H = {"User-Agent": "Mozilla/5.0"}
MAX_NEW = 40


def bigger(url):
    """Slickdeals thumbs come in several sizes; ask for the biggest."""
    return [url.replace("/300x300/", "/450x450/"), url] if "/300x300/" in url else [url]


def grab(url):
    for u in bigger(url):
        try:
            b = urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=25).read()
            im = Image.open(io.BytesIO(b)).convert("RGB")
            if min(im.size) >= 150:
                return im
        except Exception:
            continue
    return None


def main():
    deals = json.loads(Path("data/deals.json").read_text())
    PHOTOS.mkdir(exist_ok=True)
    new = 0
    for d in deals:
        a, url = d.get("asin", ""), d.get("image", "")
        if not a or not url or (PHOTOS / f"{a}.jpg").exists() or d.get("expired"):
            continue
        im = grab(url)
        if im:
            im.save(PHOTOS / f"{a}.jpg", quality=92)
            new += 1
            print("saved", a, im.size)
            if new >= MAX_NEW:
                break
    print(f"{new} new photos")


if __name__ == "__main__":
    main()
