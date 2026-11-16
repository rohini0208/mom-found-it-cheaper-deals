"""Lists the products in today's posts and Reels that still need a photo.

Run:  python need_photos.py   -> writes PHOTOS_NEEDED.md
Each line has the product's Amazon page (with your tracking tag). Open it signed in to
Associates, run the bookmarklet in PHOTOS_HOWTO.md (one click saves <ASIN>.jpg), then upload the
files to the photos/ folder on GitHub. find_photo() picks them up by ASIN. No Claude, no tokens.
"""
import json
import os
from pathlib import Path

import make_posts as mp
from make_videos import find_photo

TAG = os.environ.get("AMAZON_TAG", "momfounditc08-20")
deals = json.loads(Path("data/deals.json").read_text())
made = set()
lines = ["# Photos needed (products in the next posts that have no photo yet)", ""]
seen = set()
for cat, items in mp.pick_groups(deals, made):
    for d in items:
        a = d.get("asin")
        if a and a not in seen and not find_photo(d):
            seen.add(a)
            lines.append(f"- [ ] {a}.jpg  {d['title'][:60]}  https://www.amazon.com/dp/{a}?tag={TAG}")
if len(lines) == 2:
    lines.append("All set: every product in the next posts has a photo (or no product ID).")
Path("PHOTOS_NEEDED.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
