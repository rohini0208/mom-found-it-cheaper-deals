"""Mom Found It Cheaper - the one-place deals website.

Builds site/index.html from the collected data:
  data/deals.json          deals, codes, coupons, votes, features (deal_finder.py)
  data/price_history.json  our own price history per product (deal_finder.py)
  data/viral.json          fastest-growing product Shorts (viral_finder.py)
  data/tested.json         deals YOU marked "Tested today" (tested workflow)

Settings (GitHub repo secrets/variables, optional):
  AMAZON_TAG   your Amazon Associates tracking ID, e.g. yourname-20.
               When set, deals with a known product ID link to Amazon with your tag.
  SITE_URL     the public address of this site (for captions).
"""

import hashlib
import html
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

DATA = Path("data")
OUT = Path("site")
BRAND = "Mom Found It Cheaper"
REPO = os.environ.get("GITHUB_REPOSITORY", "rohini0208/mom-found-it-cheaper-deals")
TAG = os.environ.get("AMAZON_TAG", "").strip()
PRICE_RE = re.compile(r"\$\s?(\d[\d,]*(?:\.\d{2})?)")


def load(name, default):
    f = DATA / name
    return json.loads(f.read_text()) if f.exists() else default


def deal_id(d):
    return hashlib.sha1(d["id"].encode()).hexdigest()[:10]


def product_key(d):
    if d.get("asin"):
        return d["asin"]
    name = re.split(r"\s+(?:for\s+)?\$\d", d["title"].lower())[0]
    return re.sub(r"[^a-z0-9 ]", "", name).strip()[:60]


def price_num(s):
    m = PRICE_RE.search(s or "")
    return float(m.group(1).replace(",", "")) if m else None


def badge(d, low):
    if d.get("new"):
        return "New release"
    if d.get("bestseller"):
        return "Best seller"
    if low:
        return "Lowest price we've seen"
    if d.get("thumbs", 0) >= 30:
        return "Community favorite"
    if d.get("thumbs", 0) >= 10:
        return "Trending"
    return ""


def link_for(d):
    """Your own tagged Amazon link when possible; otherwise the source deal page."""
    if TAG and d.get("asin"):
        return f"https://www.amazon.com/dp/{d['asin']}?tag={TAG}", "Get this deal"
    return d["link"], "Get this deal"


def card(d, history, tested):
    i = deal_id(d)
    price = price_num(d.get("price"))
    pts = [p for _, p in history.get(product_key(d), [])]
    lowest = min(pts) if pts else None
    is_low = price is not None and len(pts) >= 2 and price <= lowest
    b = badge(d, is_low)
    url, label = link_for(d)
    code = d.get("code", "")
    real_code = code and code != "w/ code"
    hist_txt = ""
    if len(pts) >= 2:
        hist_txt = f"Seen {len(pts)} times · low ${lowest:,.2f} · high ${max(pts):,.2f}"
    feats = "".join(f"<li>{html.escape(f)}</li>" for f in d.get("features", [])[:3])
    tested_on = tested.get(i, "")
    tags = " ".join(filter(None, [
        "has-code" if real_code else "",
        "has-coupon" if d.get("coupon") else "",
        "under25" if price is not None and price < 25 else "",
        "tested" if tested_on else "",
    ]))
    return f"""
<article class="card {tags}" id="d-{i}" data-title="{html.escape(d['title'].lower())}">
  <div class="top">
    {f'<span class="badge">{html.escape(b)}</span>' if b else ''}
    {f'<span class="tested-badge">&#10003; Tested {html.escape(tested_on)}</span>' if tested_on else ''}
  </div>
  <h3>{html.escape(d['title'])}</h3>
  {f'<ul class="feats">{feats}</ul>' if feats else ''}
  <div class="price">
    <span class="now">{html.escape(d.get('price') or '')}</span>
    {f'<span class="was">{html.escape(d["was"])}</span>' if d.get('was') else ''}
  </div>
  {f'<button class="code" data-code="{html.escape(code)}">Code <b>{html.escape(code)}</b> <span>tap to copy</span></button>' if real_code else ''}
  {'<div class="coupon">Clip the coupon on the product page</div>' if d.get('coupon') else ''}
  {'<div class="coupon">Promo code in the deal</div>' if code == 'w/ code' else ''}
  {f'<div class="hist">{hist_txt}</div>' if hist_txt else ''}
  <div class="meta"><span class="ago" data-t="{d['seen']}"></span>{f' · +{d["thumbs"]} community votes' if d.get('thumbs') else ''}</div>
  <a class="go" href="{html.escape(url)}" target="_blank" rel="sponsored noopener">{label}</a>
  <a class="admin" href="https://github.com/{REPO}/issues/new?title=tested:+{i}&body=Tested+{html.escape(d['title'][:60])}">Mark tested today</a>
</article>"""


def viral_section(viral):
    vids = viral.get("videos", [])[:6]
    if not vids:
        return ""
    items = "".join(
        f'<a class="viral" href="{html.escape(v["url"])}" target="_blank" rel="noopener">'
        f'<b>{v["per_hour"]:,}</b><span>views/hour</span><em>{html.escape(v["title"][:70])}</em></a>'
        for v in vids)
    return f'<section><h2>Going viral this week</h2><p class="sub">Fastest-growing product videos right now</p><div class="virals">{items}</div></section>'


CSS = """
:root{--ivory:#F6F0E7;--char:#161518;--gold:#C9A46A;--muted:#7a7068;--blush:#E8BEBA}
*{box-sizing:border-box}body{margin:0;background:var(--ivory);color:var(--char);font-family:Inter,system-ui,sans-serif}
header{background:var(--char);color:var(--ivory);text-align:center;padding:42px 20px 34px}
.kicker{letter-spacing:.28em;font-size:12px;font-weight:600;color:var(--gold)}
h1{font-family:'Playfair Display',Georgia,serif;font-size:44px;margin:14px 0 6px;line-height:1.05}
h1 em{color:var(--gold);font-style:normal}
.rule{width:70px;height:2px;background:var(--gold);margin:16px auto}
header p{margin:0;color:#cfc6bb;font-size:14px}
.join{display:inline-block;margin-top:18px;border:1px solid var(--gold);color:var(--gold);padding:10px 18px;border-radius:30px;text-decoration:none;font-size:13px;letter-spacing:.12em;font-weight:600}
main{max-width:1100px;margin:0 auto;padding:24px 16px 60px}
h2{font-family:'Playfair Display',Georgia,serif;font-size:30px;margin:28px 0 4px}
.sub{color:var(--muted);margin:0 0 16px;font-size:14px}
.bar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:8px 0 18px}
.bar input{flex:1;min-width:180px;padding:11px 14px;border:1px solid #d8cfc3;border-radius:30px;background:#fff;font-size:15px}
.bar button{border:1px solid var(--char);background:none;padding:9px 14px;border-radius:30px;font-size:13px;cursor:pointer}
.bar button.on{background:var(--char);color:var(--ivory)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px}
.card{background:#fff;border-radius:18px;padding:20px;display:flex;flex-direction:column;gap:10px;box-shadow:0 1px 0 #e6ddd1}
.top{display:flex;gap:6px;flex-wrap:wrap;min-height:4px}
.badge{border:1px solid var(--gold);color:#9b7a43;font-size:11px;letter-spacing:.12em;text-transform:uppercase;padding:4px 10px;border-radius:20px;font-weight:600}
.tested-badge{background:#1f6f4a;color:#fff;font-size:11px;padding:4px 10px;border-radius:20px;font-weight:600}
.card h3{font-family:'Playfair Display',Georgia,serif;font-size:20px;line-height:1.25;margin:0}
.feats{margin:0;padding-left:18px;color:#4a443e;font-size:13px}
.price{display:flex;align-items:baseline;gap:10px}
.now{font-family:'Playfair Display',Georgia,serif;font-size:32px;font-weight:700;color:#a07c3f}
.was{color:var(--muted);text-decoration:line-through;text-decoration-color:var(--blush)}
.code{border:1px dashed var(--gold);background:var(--ivory);border-radius:10px;padding:10px;font-size:14px;cursor:pointer;text-align:left}
.code b{letter-spacing:.12em}.code span{float:right;color:var(--muted);font-size:12px}
.coupon{font-size:13px;color:#1f6f4a;font-weight:600}
.hist,.meta{font-size:12px;color:var(--muted)}
.go{margin-top:auto;background:var(--char);color:var(--ivory);text-align:center;padding:12px;border-radius:12px;text-decoration:none;font-weight:600}
.admin{display:none;font-size:12px;color:#1f6f4a;text-align:center}
body.is-admin .admin{display:block}
.virals{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}
.viral{background:var(--char);color:var(--ivory);border-radius:14px;padding:16px;text-decoration:none;display:flex;flex-direction:column;gap:2px}
.viral b{font-family:'Playfair Display',Georgia,serif;font-size:26px;color:var(--gold)}
.viral span{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#a99f93}
.viral em{font-style:normal;font-size:14px;margin-top:6px}
footer{text-align:center;color:var(--muted);font-size:12px;padding:30px 16px 50px;line-height:1.6}
"""

JS = """
const rtf=new Intl.RelativeTimeFormat('en',{numeric:'auto'});
document.querySelectorAll('.ago').forEach(e=>{const h=(Date.now()-new Date(e.dataset.t))/36e5;
 e.textContent='Posted '+(h<1?'just now':h<24?rtf.format(-Math.round(h),'hour'):rtf.format(-Math.round(h/24),'day'));});
document.querySelectorAll('.code').forEach(b=>b.onclick=()=>{navigator.clipboard&&navigator.clipboard.writeText(b.dataset.code);
 b.querySelector('span').textContent='copied!';});
let filt='all';const q=document.getElementById('q');
function apply(){const s=q.value.toLowerCase();document.querySelectorAll('.card').forEach(c=>{
 const ok=(filt==='all'||c.classList.contains(filt))&&(!s||c.dataset.title.includes(s));c.style.display=ok?'':'none';});}
document.querySelectorAll('.bar button').forEach(b=>b.onclick=()=>{document.querySelectorAll('.bar button').forEach(x=>x.classList.remove('on'));
 b.classList.add('on');filt=b.dataset.f;apply();});q.oninput=apply;
try{if(location.search.includes('admin=1'))localStorage.setItem('mfic-admin','1');
 if(localStorage.getItem('mfic-admin'))document.body.classList.add('is-admin');}catch(e){}
"""


def main():
    deals = load("deals.json", [])
    history = load("price_history.json", {})
    viral = load("viral.json", {})
    tested = load("tested.json", {})
    now = datetime.now(timezone.utc).strftime("%b %d, %Y %H:%M UTC")
    # tested deals first, then deals with codes, then newest
    def rank(d):
        i = deal_id(d)
        return (1 if i in tested else 0, 1 if d.get("code") and d["code"] != "w/ code" else 0, d["seen"])
    cards = "".join(card(d, history, tested) for d in sorted(deals, key=rank, reverse=True))
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{BRAND} | Daily Deals, Viral Finds & Promo Codes</title>
<meta name="description" content="A Tampa mom's daily finds: viral and proven products, promo codes, coupons and price drops in one place.">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Playfair+Display:ital,wght@0,600;0,700;1,400&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body>
<header><div class="kicker">A TAMPA MOM'S DAILY FINDS</div>
<h1>Mom Found<br><em>It Cheaper</em></h1><div class="rule"></div>
<p>Viral finds · promo codes · price drops — all in one place. Updated {now}.</p>
<a class="join" href="https://www.facebook.com/groups/1815840112666601" target="_blank" rel="noopener">JOIN THE FREE FACEBOOK GROUP</a></header>
<main>
{viral_section(viral)}
<section><h2>Today's deals</h2><p class="sub">{len(deals)} deals from the last 3 days. Codes marked &#10003; were tested by me.</p>
<div class="bar"><input id="q" placeholder="Search deals…">
<button class="on" data-f="all">All</button><button data-f="has-code">Codes</button>
<button data-f="has-coupon">Coupons</button><button data-f="under25">Under $25</button><button data-f="tested">Tested</button></div>
<div class="grid">{cards}</div></section>
</main>
<footer>As an Amazon Associate I earn from qualifying purchases. Links on this page may be affiliate links (#ad).<br>
Prices and codes change quickly — always check the final price before you buy.<br>
Deal sources: Slickdeals and DealNews community feeds, with thanks.</footer>
<script>{JS}</script></body></html>"""
    OUT.mkdir(exist_ok=True)
    (OUT / "index.html").write_text(page)
    (OUT / ".nojekyll").write_text("")
    print(f"site built: {len(deals)} deals, {len(viral.get('videos', []))} viral, {len(tested)} tested")


if __name__ == "__main__":
    main()
