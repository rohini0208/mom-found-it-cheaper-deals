"""Quality gate. Runs before any Reel or post is made. Stricter than "it parsed".

check(deal) -> list of BLOCK reasons (deal is skipped) and WARN notes (deal kept, listed in the report).
Run:  python qa.py        -> writes QA_REPORT.md for today's deals
"""

import re
from collections import Counter
from pathlib import Path

BAD_TITLE = re.compile(r"(\.\.\.|…|&amp;|&#\d+;|<[^>]+>|\?\?)")
MIN_TITLE_WORDS = 2


def _num(p):
    try:
        return float(str(p).replace("$", "").replace(",", ""))
    except ValueError:
        return None


def check(deal):
    block, warn = [], []
    price, was = _num(deal.get("price", "")), _num(deal.get("was", ""))
    title = deal.get("title", "")
    if price is None or price <= 0:
        block.append("no price")
    if deal.get("expired"):
        block.append("marked expired")
    if re.match(r"^\s*[$\[]", title) or re.search(r"\bYMMV\b", title):
        block.append("title is a price fragment or store tag")
    if len(title.split()) < MIN_TITLE_WORDS:
        block.append("title too short")
    if BAD_TITLE.search(title):
        warn.append("title has cut-off or garbled text")
    if price and was and price >= was:
        block.append("price not below was-price")
    if price and was and price < was * 0.1:
        block.append("price under 10% of was-price (likely a data error)")
    code = deal.get("code", "")
    if code and code != "w/ code" and deal.get("code_label") in ("expired", "may be expired"):
        warn.append("code may be expired, will be hidden")
    if "amazon" in (deal.get("store", "") or "").lower() and not deal.get("asin"):
        warn.append("Amazon deal without product ID (no affiliate link, no price check)")
    return block, warn


def dup_wording(texts):
    """Flag captions that share the same first 8 words."""
    seen = Counter(" ".join(t.split()[:8]).lower() for t in texts)
    return [k for k, v in seen.items() if v > 1]


def main():
    import json
    deals = json.loads(Path("data/deals.json").read_text())
    blocked, warned = Counter(), Counter()
    for d in deals:
        b, w = check(d)
        blocked.update(b)
        warned.update(w)
    lines = [f"# QA report ({len(deals)} deals)", "", "## Blocked (never posted)"]
    lines += [f"- {k}: {v}" for k, v in blocked.most_common()] or ["- none"]
    lines += ["", "## Warnings (posted, but check)"]
    lines += [f"- {k}: {v}" for k, v in warned.most_common()] or ["- none"]
    Path("QA_REPORT.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
