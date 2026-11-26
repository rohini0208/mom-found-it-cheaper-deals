"""Merge Grok's deal list into data/deals.json as source "Grok" (unverified until the Lenovo run checks the
Amazon page: title match, buyable, price). Drop pipe rows into data/grok/YYYY-MM-DD.txt and run:
    python grok_import.py
Rows: ASIN | name | current price | list price | why
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from deal_finder import category_of

DEALS = Path("data/deals.json")
ASIN = re.compile(r"^[A-Z0-9]{10}$")


def main():
    deals = json.loads(DEALS.read_text()) if DEALS.exists() else []
    have = {d.get("asin") for d in deals if d.get("asin")}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    added = 0
    for f in sorted(Path("data/grok").glob("*.txt")):
        for line in f.read_text().splitlines():
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 3 or not ASIN.match(parts[0]) or parts[0] in have:
                continue
            asin, name, price = parts[0], parts[1], parts[2]
            if re.search(r"\(alt|\(confirm|\(live", name):
                continue
            why = parts[4] if len(parts) > 4 else ""
            deals.append({
                "id": f"grok:{asin}", "title": name, "link": f"https://www.amazon.com/dp/{asin}", "asin": asin,
                "price": price, "store": "Amazon", "source": "Grok", "seen": now, "thumbs": 0,
                "category": category_of(name), "features": [why] if why else [],
            })
            have.add(asin)
            added += 1
    DEALS.write_text(json.dumps(deals, indent=0))
    print(f"grok import: +{added} (verified only after the Lenovo link check)")


if __name__ == "__main__":
    main()
