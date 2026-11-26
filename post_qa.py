"""Pre-publish QA for posts. Reads posts/manifest.json + captions + PNGs, flags anything a shopper could call wrong.
BLOCKER = post is moved to posts/blocked/ and removed from webposts/ (never goes out). WARN = listed in POST_QA.md."""
import json, os, re, shutil, sys, time
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


STRICT = os.environ.get("POST_QA_STRICT", "0") == "1"      # 1 = unverified-by-Amazon-page data blocks the post
STOP = set("the a an and with for of in to on by new pack set pcs pc piece inch oz black white blue red green pink gray grey silver gold only just from amazon shipped shipping prime free off sale deal deals count women womens mens men's per each select members member at via after coupon code subscribe save black friday early".split())
VARIANT = {"black", "white", "blue", "red", "green", "pink", "gray", "grey", "silver", "gold", "rose", "navy", "purple", "brown", "beige", "twin", "full", "queen", "king"}


def words(s):
    return {w for w in re.findall(r"[a-z0-9]+", (s or "").lower()) if len(w) > 2 and w not in STOP}


def page_checks(i, out):
    """Compare each product with what Amazon's own page said when the Lenovo last looked."""
    m = META.get(i["asin"]) or {}
    nm = i["title"][:40]
    sev = "BLOCKER" if STRICT else "WARN"
    ck = m.get("checked")
    if not ck:
        out.append((sev, f"never verified against the live Amazon page (v4): {nm}"))
        return
    age = (time.time() - ck) / 3600
    if age > 36:
        out.append((sev, f"Amazon page data is {age:.0f}h old: {nm}"))
    av = (m.get("avail") or "").lower()
    if "unavailable" in av or "out of stock" in av:
        out.append(("BLOCKER", f"Amazon says unavailable: {nm}"))
    sl = (m.get("seller") or "").lower()
    if m.get("v", 0) < 5 and "resale" in sl:
        sl = ""          # v4 runs read the 'Used - Like New / Amazon Resale' box, not the buy box (verified 2026-11-26 on 2 ASINs)
    if "resale" in sl or "warehouse" in sl or "renewed" in (m.get("title") or "").lower():
        out.append(("BLOCKER", f"used/open-box seller ({m.get('seller','')[:30]}): {nm}"))
    at = m.get("title") or ""
    if at:
        ours, theirs = words(i["title"]), words(at)
        if ours and theirs and len(ours & theirs) / min(len(ours), len(theirs)) < 0.5:   # Amazon title may be stored truncated
            out.append(("BLOCKER", f"title does not match Amazon page title '{at[:50]}': {nm}"))
        mine = {w for w in re.findall(r"[a-z]+", i["title"].lower()) if w in VARIANT}
        page = {w for w in re.findall(r"[a-z]+", (m.get("color", "") + " " + m.get("size", "") + " " + m.get("style", "")).lower()) if w in VARIANT}
        if page and mine and not (mine & page):
            out.append(("BLOCKER", f"variant on Amazon page ({', '.join(sorted(page))}) differs from our title: {nm}"))
        elif page and not mine:
            out.append(("WARN", f"price may only apply to variant '{m.get('color') or m.get('size')}' - name it: {nm}"))
    if i.get("code") and i["code"].lower() not in (m.get("promo") or "").lower():
        out.append(("BLOCKER", f"code {i['code']} not confirmed on Amazon page: {nm}"))


def check_post(p, text):
    out = []                                        # (severity, message)
    items = p["items"]
    asins = [i["asin"] for i in items]
    cap = text.split("FIRST COMMENT")[0]
    cmt = text.split("FIRST COMMENT")[-1].split("\n", 1)[-1]
    if "Amazon Associate" not in cap:
        out.append(("BLOCKER", "caption missing Amazon Associate disclosure"))
    if not cap.split("CAPTION:")[-1].strip().startswith("#ad"):
        out.append(("BLOCKER", "caption must start with #ad (FTC: disclosure before the 'See more' fold)"))
    if "#ad" not in cmt.split("\n")[0]:
        out.append(("BLOCKER", "first comment must start with #ad"))
    if cap.count("#ad") > 1:
        out.append(("WARN", "more than one #ad in the caption"))
    if re.search(r"camelcamelcamel|slickdeals|dealnews|hip2save|keepa", text, re.I):
        out.append(("BLOCKER", "third-party deal/price-tracker site named in the post"))
    if re.search(r"[\u200b\u200c\u200d\ufeff]", text):
        out.append(("BLOCKER", "zero-width character in the post text"))
    if re.search(r"I'd grab it|Mia's pick", text):
        out.append(("BLOCKER", "first-person endorsement from the AI persona (FTC endorsement guides)"))
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
        if i.get("asin"):
            page_checks(i, out)
    pf = POSTS / f"{p['file']}.png"
    tf = POSTS / f"{p['file']}.txt"
    if pf.exists() and tf.exists() and abs(pf.stat().st_mtime - tf.stat().st_mtime) > 600:
        out.append(("BLOCKER", "image and caption were generated at different times (stale file mix)"))
    for i in items:
        if not i.get("asin"):
            continue
        cap_has = re.search(r"\b" + re.escape(re.sub(r"\W+", " ", i["title"]).split()[0].lower()) + r"\b", re.sub(r"\W+", " ", cap).lower()) if i["title"].split() else True
        if not cap_has and p["kind"] in ("single", "quick"):
            out.append(("WARN", f"caption never names the product: {i['title'][:40]}"))
    for i in items:
        if not i["asin"]:
            out.append(("BLOCKER", f"no ASIN: {i['title'][:40]}"))
        m = META.get(i["asin"]) or {}
        now, price = num(m.get("now")), num(i["price"])
        if now and price and price < now * 0.7:
            out.append(("BLOCKER", f"price ${price} well below Amazon page ${now} (coupon?): {i['title'][:40]}"))
        if now and price and abs(price - now) / now > 0.08:
            out.append(("BLOCKER", f"post price ${price} differs >8% from Amazon page ${now}: {i['title'][:40]}"))
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
