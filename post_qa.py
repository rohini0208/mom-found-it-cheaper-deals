"""Pre-publish QA for posts. Reads posts/manifest.json + captions + PNGs, flags anything a shopper could call wrong.
BLOCKER = post is moved to posts/blocked/ and removed from webposts/ (never goes out). WARN = listed in POST_QA.md."""
import json, re, shutil, sys
from pathlib import Path

TAG = "momfounditc08-20"
POSTS, WEB = Path("posts"), Path("webposts")
META = json.loads(Path("data/product_meta.json").read_text()) if Path("data/product_meta.json").exists() else {}
JUNK = re.compile(r"^\[|\$\d|\bAC$| at$|:$| -$|\|", re.I)
DANGLING = {"of", "and", "with", "for", "the", "a", "to", "in", "on", "&", "-", "x", "w/"}
AUD = {"w": "women's", "m": "men's", "k": "kids'", "any": ""}


def num(s):
    m = re.search(r"[\d,]+\.?\d*", str(s or ""))
    return float(m.group().replace(",", "")) if m else None


def check_post(p, text):
    out = []                                        # (severity, message)
    items = p["items"]
    asins = [i["asin"] for i in items]
    cap = text.split("FIRST COMMENT")[0]
    cmt = text.split("FIRST COMMENT")[-1].split("\n", 1)[-1]
    if "Amazon Associate" not in cap:
        out.append(("BLOCKER", "caption missing Amazon Associate disclosure"))
    if not (POSTS / f"{p['file']}.png").exists():
        out.append(("BLOCKER", "image missing"))
    links = re.findall(r"https?://\S+", cmt)
    amz = [l for l in links if "amazon.com" in l]
    if len(amz) < len(items):
        out.append(("BLOCKER", f"{len(items)} products but {len(amz)} Amazon links in first comment"))
    for l in amz:
        if f"tag={TAG}" not in l:
            out.append(("BLOCKER", f"untagged Amazon link {l[:60]}"))
    for l in amz:
        if not any(a and a in l for a in asins):
            out.append(("BLOCKER", f"link ASIN not in this post's products: {l[:60]}"))
    for i in items:
        if not i["asin"]:
            out.append(("BLOCKER", f"no ASIN: {i['title'][:40]}"))
        m = META.get(i["asin"]) or {}
        now, price = num(m.get("now")), num(i["price"])
        if now and price and price < now * 0.7:
            out.append(("BLOCKER", f"price ${price} well below Amazon page ${now} (coupon?): {i['title'][:40]}"))
        if now and price and price > now * 1.15:
            out.append(("BLOCKER", f"price ${price} above Amazon page ${now}: {i['title'][:40]}"))
        if i["pct"] and i["pct"] >= 15:
            lst = num(m.get("list"))
            if not lst or lst <= (price or 0):
                out.append(("BLOCKER", f"claims {i['pct']}% off without a valid list price: {i['title'][:40]}"))
        if (m.get("rating") or 5) < 3.8 and (m.get("reviews") or 0) >= 20:
            out.append(("BLOCKER", f"low rating {m.get('rating')}: {i['title'][:40]}"))
    if len(set(asins)) < len(asins):
        out.append(("BLOCKER", "same product twice in one post"))
    # names as written in the comment must not look cut off or junky
    for line in cmt.splitlines():
        mm = re.match(r"(?:\d+% OFF - )?(.+?)(?: - (?:code|clip).*)?$", line)
        if mm and not line.startswith(("http", "Shop", "Price", "As an", "A:", "B:")) and line.strip():
            name = mm.group(1).strip()
            if JUNK.search(name) or name.split()[-1].lower().strip(".,;:") in DANGLING:
                out.append(("WARN", f"name looks cut/junky: '{name}'"))
    if p["kind"] == "thisorthat":
        a, b = items
        if a["who"] != b["who"]:
            out.append(("BLOCKER", f"THIS-or-THAT mixes audiences ({AUD[a['who']] or 'any'} vs {AUD[b['who']] or 'any'})"))
        if not set(a["kind"]) & set(b["kind"]):
            out.append(("BLOCKER", "THIS-or-THAT products are different types"))
        if a["category"] != b["category"]:
            out.append(("BLOCKER", "THIS-or-THAT different categories"))
        pa, pb = num(a["price"]), num(b["price"])
        if pa and pb and max(pa, pb) > 1.8 * min(pa, pb) + 5:
            out.append(("BLOCKER", f"THIS-or-THAT prices too far apart (${pa} vs ${pb})"))
    m = re.search(r"under \$(\d+)", p["theme"], re.I)
    if m:
        cap_price = float(m.group(1))
        for i in items:
            if (num(i["price"]) or 0) > cap_price:
                out.append(("BLOCKER", f"theme '{p['theme']}' but {i['title'][:30]} costs {i['price']}"))
    if p["kind"] == "group":
        whos = {i["who"] for i in items} - {"any"}
        if len(whos) > 1:
            out.append(("WARN", "group mixes men's/women's/kids' items"))
        cats = {i["category"] for i in items}
        if len(cats) > 2 and "under" not in p["theme"].lower():
            out.append(("WARN", f"group spans {len(cats)} categories"))
    return out


def main():
    mf = POSTS / "manifest.json"
    if not mf.exists():
        print("no manifest; nothing to check")
        return 0
    manifest = json.loads(mf.read_text())
    seen, report, blocked = {}, [], 0
    for p in manifest:
        txt = POSTS / f"{p['file']}.txt"
        text = txt.read_text() if txt.exists() else ""
        issues = check_post(p, text)
        for i in p["items"]:
            if i["asin"] in seen and p["kind"] != "single":
                issues.append(("BLOCKER", f"duplicate product also in {seen[i['asin']]}: {i['title'][:40]}"))
            seen.setdefault(i["asin"], p["file"])
        bad = any(s == "BLOCKER" for s, _ in issues)
        report.append((p["file"], p["theme"], issues, bad))
        if bad:
            blocked += 1
            (POSTS / "blocked").mkdir(exist_ok=True)
            for ext in ("png", "txt"):
                f = POSTS / f"{p['file']}.{ext}"
                if f.exists():
                    shutil.move(str(f), POSTS / "blocked" / f.name)
            w = WEB / f"{p['file']}.png"
            if w.exists():
                w.unlink()
    lines = ["# Post QA", ""]
    for f, th, iss, bad in report:
        lines.append(f"## {f} ({th}): {'BLOCKED' if bad else 'ok' if not iss else 'ok with warnings'}")
        lines += [f"- {s}: {m}" for s, m in iss]
    Path("POST_QA.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"{blocked} of {len(report)} posts blocked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
