"""Group cover 1640x856: warm gradient, big name, promise line, 3 real product cards with price + % off badges.
Safe area: Facebook crops the sides on mobile, so key text sits in the middle ~60%."""
import json, sys
sys.path.insert(0, ".")
from PIL import Image, ImageDraw, ImageOps, ImageFilter
import make_posts as mp
from make_videos import sans

W, H = 1640, 856
img = Image.new("RGB", (W, H))
px = img.load()
for y in range(H):
    for x in range(W):
        t = (x / W * 0.55 + y / H * 0.45)
        px[x, y] = (int(255 - 20 * t), int(143 + 70 * t), int(0 + 30 * t))
d = ImageDraw.Draw(img)
INK = (36, 28, 20)
# product cards (top deals with photo, was price and good rating)
deals = json.load(open("data/deals.json"))
meta = json.load(open("data/product_meta.json"))
cands = [x for x in deals if mp.is_amazon(x) and x.get("asin") and mp.find_photo(x) and mp.pct_off(x) >= 25
         and (meta.get(x["asin"]) or {}).get("rating", 0) >= 4.3 and mp.price_value(x.get("price", "")) and 5 <= mp.price_value(x["price"]) <= 60
         and not mp.qa_check(x)[0] and not any(w in x["title"].lower() for w in mp.SKIP_WORDS)]
cands.sort(key=mp.score, reverse=True)
cards, seen, cats = [], set(), set()
for c in cands:
    k = mp.product_key(c)
    if k not in seen and c.get("category") not in cats:     # three different kinds of products
        seen.add(k)
        cats.add(c.get("category"))
        cards.append(c)
    if len(cards) == 3:
        break
cw, ch = 330, 430
x0 = (W - (3 * cw + 2 * 36)) // 2
y0 = 400
for i, c in enumerate(cards):
    x = x0 + i * (cw + 36)
    sh = Image.new("RGBA", (cw + 40, ch + 40), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([20, 26, cw + 20, ch + 26], 30, fill=(0, 0, 0, 90))
    img.paste(sh.filter(ImageFilter.GaussianBlur(14)), (x - 20, y0 - 20), sh.filter(ImageFilter.GaussianBlur(14)))
    d.rounded_rectangle([x, y0, x + cw, y0 + ch], 30, fill=(255, 255, 255))
    pic = ImageOps.contain(Image.open(mp.find_photo(c)).convert("RGB"), (cw - 40, 270))
    img.paste(pic, (x + (cw - pic.width) // 2, y0 + 20 + (270 - pic.height) // 2))
    lab = {"Toys & Games": "TOYS & GAMES", "Home & Kitchen": "HOME & KITCHEN", "Tech & Electronics": "TECH & GADGETS", "Fashion": "STYLE",
           "Beauty & Health": "BEAUTY & HEALTH", "Baby & Kids": "KIDS", "Pets": "PETS", "Outdoor & Tools": "OUTDOORS",
           "Grocery & Household": "HOUSEHOLD"}.get(c.get("category"), "DAILY FINDS")
    lf = sans(30, "Bold")
    d.text((x + (cw - d.textlength(lab, font=lf)) / 2, y0 + ch - 70), lab, font=lf, fill=(27, 94, 32))
# headline
def center(y, text, font, fill):
    d.text(((W - d.textlength(text, font=font)) / 2, y), text, font=font, fill=fill)
center(60, "MOM FOUND IT CHEAPER", sans(112, "Bold"), (255, 255, 255))
center(196, "Real Amazon deals. Checked daily. With the was-price.", sans(46, "SemiBold"), INK)
pills = [("UNDER $10 FINDS", (46, 125, 50)), ("GIFT IDEAS", (0, 121, 107)), ("STAR RATINGS", (21, 101, 192))]
pf2 = sans(32, "Bold")
total = sum(d.textlength(t, font=pf2) + 56 for t, _ in pills) + 24 * (len(pills) - 1)
x = (W - total) / 2
for t, col in pills:
    w = d.textlength(t, font=pf2) + 56
    d.rounded_rectangle([x, 276, x + w, 276 + 70], 35, fill=col)
    d.text((x + 28, 276 + 15), t, font=pf2, fill=(255, 255, 255))
    x += w + 24
center(364 - 6, "Free group  -  join and save", sans(30, "SemiBold"), INK) if False else None
img.save("launch/group_cover2.png")
print("cover2 saved with", len(cards), "cards")
