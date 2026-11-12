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
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from deal_finder import is_amazon, no_price_title

DATA = Path("data")
OUT = Path("site")
BRAND = "Mom Found It Cheaper"
REPO = os.environ.get("GITHUB_REPOSITORY", "rohini0208/mom-found-it-cheaper-deals")
TAG = os.environ.get("AMAZON_TAG", "momfounditc08-20").strip()  # Amazon Associates tracking ID
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
    t = tested.get(i, "")            # "Nov 12" (old) or {"date": ..., "asin": ...}
    price = price_num(d.get("price"))
    pts = [p for _, p in history.get(product_key(d), [])]
    lowest = min(pts) if pts else None
    is_low = price is not None and len(pts) >= 2 and price <= lowest
    b = badge(d, is_low)
    if isinstance(t, dict) and t.get("asin") and not d.get("asin"):
        d = dict(d, asin=t["asin"])      # Amazon link you pasted when testing
    url, label = link_for(d)
    amz = is_amazon(d)
    if amz:                      # Amazon policy: no prices unless from Amazon's API
        price, pts, b = None, [], (b if b != "Lowest price we've seen" else "")
    code = d.get("code", "")
    real_code = code and code != "w/ code"
    hist_txt = ""
    if len(pts) >= 2:
        hist_txt = f"Seen {len(pts)} times · low ${lowest:,.2f} · high ${max(pts):,.2f}"
    feats = "".join(f"<li>{html.escape(f)}</li>" for f in d.get("features", [])[:3])
    tested_on = t.get("date", "") if isinstance(t, dict) else t
    tags = " ".join(filter(None, [
        "has-code" if real_code else "",
        "has-coupon" if d.get("coupon") else "",
        "under25" if price is not None and price < 25 else "",
        "tested" if tested_on else "",
    ]))
    return f"""
<article class="card {tags}" id="d-{i}" data-title="{html.escape((no_price_title(d['title']) if amz else d['title']).lower())}" data-cat="{html.escape(d.get('category','Everything else'))}" data-store="{html.escape(d.get('store','Other'))}">
  <div class="where">{html.escape(d.get('store','Other'))} · {html.escape(d.get('category','Everything else'))}</div>
  <div class="top">
    {f'<span class="badge">{html.escape(b)}</span>' if b else ''}
    {f'<span class="tested-badge">&#10003; Tested {html.escape(tested_on)}</span>' if tested_on else ''}
  </div>
  <h3>{html.escape(no_price_title(d['title']) if amz else d['title'])}</h3>
  {f'<ul class="feats">{feats}</ul>' if feats else ''}
  {'<div class="amz">Price drop on Amazon &middot; tap to see today&rsquo;s price</div>' if amz else f"""<div class="price">
    <span class="now">{html.escape(d.get('price') or '')}</span>
    {f'<span class="was">{html.escape(d["was"])}</span>' if d.get('was') else ''}
  </div>"""}
  {f'<button class="code" data-code="{html.escape(code)}">Code <b>{html.escape(code)}</b> <span>tap to copy</span></button>' if real_code else ''}
  {'<div class="coupon">Clip the coupon on the product page</div>' if d.get('coupon') else ''}
  {'<div class="coupon">Promo code in the deal</div>' if code == 'w/ code' else ''}
  {f'<div class="hist">{hist_txt}</div>' if hist_txt else ''}
  <div class="meta"><span class="ago" data-t="{d['seen']}"></span>{f' · +{d["thumbs"]} community votes' if d.get('thumbs') else ''}</div>
  <a class="go" href="{html.escape(url)}" target="_blank" rel="sponsored noopener">{label}</a>
  <a class="admin" href="https://github.com/{REPO}/issues/new?title=tested:+{i}&body=Paste+the+Amazon+product+link+here+(optional):%0A%0ATested:+{html.escape(urllib.parse.quote_plus(d['title'][:60]))}">Mark tested today</a>
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
.cats{display:flex;gap:8px;overflow-x:auto;padding:4px 0 10px;margin-top:6px}
.cats button{flex:none;border:1px solid #d8cfc3;background:#fff;padding:8px 14px;border-radius:30px;font-size:13px;cursor:pointer;white-space:nowrap}
.cats button.on{background:var(--gold);border-color:var(--gold);color:#fff}.cats small{opacity:.7}
.bar select{padding:10px 12px;border:1px solid #d8cfc3;border-radius:30px;background:#fff;font-size:14px}
.where{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
footer a{color:var(--muted)}
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
.amz{font-size:15px;font-weight:600;color:#a07c3f}
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
let filt='all',cat='';const q=document.getElementById('q'),st=document.getElementById('store');
function apply(){const s=q.value.toLowerCase(),sv=st.value;document.querySelectorAll('.card').forEach(c=>{
 const ok=(filt==='all'||c.classList.contains(filt))&&(!s||c.dataset.title.includes(s))&&(!cat||c.dataset.cat===cat)&&(!sv||c.dataset.store===sv);
 c.style.display=ok?'':'none';});}
document.querySelectorAll('.cats button').forEach(b=>b.onclick=()=>{document.querySelectorAll('.cats button').forEach(x=>x.classList.remove('on'));
 b.classList.add('on');cat=b.dataset.c;apply();});st.onchange=apply;
document.querySelectorAll('.bar button').forEach(b=>b.onclick=()=>{document.querySelectorAll('.bar button').forEach(x=>x.classList.remove('on'));
 b.classList.add('on');filt=b.dataset.f;apply();});q.oninput=apply;
try{if(location.search.includes('admin=1'))localStorage.setItem('mfic-admin','1');
 if(localStorage.getItem('mfic-admin'))document.body.classList.add('is-admin');}catch(e){}
"""


LEGAL_UPDATED = "November 12, 2026"
LEGAL = {
"disclosure.html": ("Affiliate disclosure", """
<p>Mom Found It Cheaper ("we", "us") shares deals on products sold by other companies. Many links on our website, Facebook group,
videos and other channels are <b>affiliate links</b>. If you click one and buy something, we may earn a small commission from the
retailer or brand. <b>It costs you nothing extra.</b></p>
<p><b>Amazon:</b> As an Amazon Associate I earn from qualifying purchases.</p>
<p>We may also earn from other affiliate programs (for example Walmart, Target, eBay or brand programs) and from brands that pay to
feature a deal. Sponsored or paid posts are always labeled <b>#ad</b> or <b>Sponsored</b>.</p>
<p>Commissions never change the price you pay. We only share deals we think are worth your time, but you should always decide for
yourself whether a product is right for you.</p>"""),
"terms.html": ("Terms &amp; conditions", """
<p>By using this website, our Facebook group or any of our channels, you agree to these terms. If you do not agree, please do not use them.</p>
<h3>1. Information only</h3><p>Everything we share is general shopping information, not professional, financial, medical or safety advice.
Product descriptions, features, prices and ratings come from deal listings and retailers. We try to be accurate but we do not guarantee that
any information is complete, current or correct.</p>
<h3>2. Prices, coupons and codes</h3><p>Prices, stock, coupons and promo codes are set by retailers and can change, sell out or expire at any time,
sometimes within minutes. A code marked "Tested" worked for us on the date shown; it may not work for you or later. "Lowest price we've seen"
compares only prices we have recorded. Always check the final price at checkout before you buy.</p>
<h3>3. We are not the seller</h3><p>All purchases are made directly with the retailer. We do not sell products, take payments, ship orders, or handle
returns, refunds, warranties or product safety. Any issue with an order is between you and the retailer or manufacturer.</p>
<h3>4. Third-party sites</h3><p>Our links take you to websites we do not own or control. Their own terms and privacy policies apply. We are not
responsible for their content, products, services or practices.</p>
<h3>5. Affiliate links</h3><p>Some links earn us a commission. See our <a href="disclosure.html">affiliate disclosure</a>.</p>
<h3>6. Community rules</h3><p>In our Facebook group and other channels: be kind; no spam, selling, self-promotion or referral links; no scams,
counterfeit goods or misleading posts. We may remove posts or members at our discretion.</p>
<h3>7. No warranty</h3><p>Our website and channels are provided "as is" and "as available", without warranties of any kind.</p>
<h3>8. Limitation of liability</h3><p>To the fullest extent allowed by law, Mom Found It Cheaper and its owners are not liable for any loss or damage
arising from your use of our content, links or any product or retailer, including expired deals, price changes, or product problems.</p>
<h3>9. Trademarks</h3><p>Amazon and all other store and brand names are trademarks of their owners. We are not affiliated with or endorsed by them
unless we say so.</p>
<h3>10. Changes</h3><p>We may update these terms at any time. The date below shows the latest version.</p>
<h3>11. Governing law</h3><p>These terms are governed by the laws of the State of Florida, USA.</p>"""),
"privacy.html": ("Privacy policy", """
<p>We respect your privacy. This website does not ask you to create an account and does not collect your name, email or payment details.</p>
<h3>What is collected</h3><p>Our hosting provider (Cloudflare) may record basic technical information such as your IP address, browser and
pages visited, for security and performance. Fonts are loaded from Google Fonts, which may receive your IP address. Your browser may store
a small preference (for example, filters you used) on your own device.</p>
<h3>Affiliate partners</h3><p>When you click a link to a retailer such as Amazon, that retailer may use cookies to track the visit and any
purchase so we can be credited. Their privacy policies apply once you leave our site.</p>
<h3>Facebook group</h3><p>If you join our Facebook group, Facebook's own privacy policy applies to what you share there.</p>
<h3>Children</h3><p>Our content is meant for adults and is not directed at children under 13.</p>
<h3>Contact</h3><p>Questions? Message us through our Facebook group.</p>"""),
}


def legal_page(title, body):
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} | {BRAND}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Playfair+Display:wght@700&display=swap" rel="stylesheet">
<style>{CSS} main{{max-width:760px}} main p,main li{{line-height:1.65;font-size:15px}} main h3{{font-family:'Playfair Display',Georgia,serif;margin:22px 0 6px}}</style></head>
<body><header><div class="kicker"><a href="index.html" style="color:inherit;text-decoration:none">&larr; MOM FOUND IT CHEAPER</a></div><h1>{title}</h1></header>
<main>{body}<p style="color:#7a7068;font-size:13px">Last updated {LEGAL_UPDATED}.</p></main></body></html>"""


def main():
    from deal_finder import category_of, store_of
    deals = load("deals.json", [])
    for d in deals:                      # older saved deals: tag them now
        d.setdefault("category", category_of(d["title"]))
        d.setdefault("store", store_of(d["title"] + " " + d.get("desc", "")))
    history = load("price_history.json", {})
    viral = load("viral.json", {})
    tested = load("tested.json", {})
    now = datetime.now(timezone.utc).strftime("%b %d, %Y %H:%M UTC")
    # tested deals first, then deals with codes, then newest
    def rank(d):
        i = deal_id(d)
        return (1 if i in tested else 0, 1 if d.get("code") and d["code"] != "w/ code" else 0, d["seen"])
    PER_CATEGORY = 100
    count, picked = {}, []
    for d in sorted(deals, key=rank, reverse=True):
        c = d.get("category", "Everything else")
        if count.get(c, 0) < PER_CATEGORY:
            count[c] = count.get(c, 0) + 1
            picked.append(d)
    cats = sorted(count, key=lambda c: (c == "Everything else", -count[c]))
    stores = sorted({d.get("store", "Other") for d in picked}, key=lambda s: (s == "Other", s))
    cat_buttons = "".join(f'<button data-c="{html.escape(c)}">{html.escape(c)} <small>{count[c]}</small></button>' for c in cats)
    store_opts = "".join(f'<option>{html.escape(s)}</option>' for s in stores)
    cards = "".join(card(d, history, tested) for d in picked)
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
<section><h2>Today's deals</h2><p class="sub">{len(picked)} deals across {len(cats)} categories from the last 3 days — top 100 per category. Codes marked &#10003; were tested by me personally.</p>
<div class="cats"><button class="on" data-c="">All categories</button>{cat_buttons}</div>
<div class="bar"><input id="q" placeholder="Search deals…"><select id="store"><option value="">All stores</option>{store_opts}</select>
<button class="on" data-f="all">All</button><button data-f="has-code">Codes</button>
<button data-f="has-coupon">Coupons</button><button data-f="under25">Under $25</button><button data-f="tested">Tested</button></div>
<div class="grid">{cards}</div></section>
</main>
<footer><b>Affiliate disclosure:</b> As an Amazon Associate I earn from qualifying purchases. Some links are affiliate links (#ad) — if you buy through them we may earn a commission at no extra cost to you.<br>
Prices, availability, coupons and promo codes are set by the retailers and can change or expire at any time. Always check the final price at checkout before you buy.
We are not the seller and do not handle orders, shipping, returns or warranties — contact the retailer for those.
"Tested" means we personally saw the code work on the date shown; it may not work for you or later.
"Lowest price we've seen" is based only on prices we have recorded, not a guarantee of an all-time low. Product details come from the deal listing and the retailer; we do not guarantee them.<br>
Deal sources: Slickdeals and DealNews community feeds, with thanks. Amazon and other store names are trademarks of their owners; we are not affiliated with or endorsed by them.<br>
<a href="disclosure.html">Affiliate disclosure</a> · <a href="terms.html">Terms &amp; conditions</a> · <a href="privacy.html">Privacy policy</a></footer>
<script>{JS}</script></body></html>"""
    OUT.mkdir(exist_ok=True)
    (OUT / "index.html").write_text(page)
    for name, (title, body) in LEGAL.items():
        (OUT / name).write_text(legal_page(title, body))
    (OUT / ".nojekyll").write_text("")
    print(f"site built: {len(deals)} deals, {len(viral.get('videos', []))} viral, {len(tested)} tested")


if __name__ == "__main__":
    main()
