"""Mom Found It Cheaper - faceless deal Reels.

Picks the best new deals from data/deals.json and makes a 1080x1920
vertical video for each: hook, product, price, code, call to action,
with an AI voiceover (free Microsoft Edge voices via edge-tts).
No product photos are used (Amazon rules), so it is text-and-motion.

Run:  python make_videos.py            (needs: pip install pillow edge-tts, and ffmpeg)
Out:  videos/deal_1.mp4 + deal_1.txt (caption to paste), ...
"""

import asyncio
import hashlib
from copy_bank import CLOSERS, FEATURES_TITLES, OPENERS, hook_for, pick
from qa import check as qa_check
import json
import os


def _sft(_t, _fmt):
    """strftime that works on Windows too: %-d/%-I are glibc-only, Windows needs %#d/%#I."""
    return _t.strftime(_fmt.replace("%-", "%#") if os.name == "nt" else _fmt)
import random
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from deal_finder import is_amazon, no_price_title
from trends_finder import load_signals, viral_sources

SIGNALS = load_signals()

# "show" (default): Amazon prices shown with an "as of" time; "hide": no Amazon prices
AMAZON_PRICES = os.environ.get("AMAZON_PRICES", "show").strip().lower()


def as_of(iso):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    t = datetime.fromisoformat(iso).astimezone(ZoneInfo("America/New_York"))
    return _sft(t, "%b %-d, %-I:%M %p ET")

W, H = 1080, 1920
BRAND = "Mom Found It Cheaper"
VOICE = os.environ.get("VOICE") or "en-US-AvaMultilingualNeural"   # warm, expressive; pick yours from the voice samples
# A/B test: every other Reel uses this voice instead (set AB_VOICE to "off" to stop the test)
AB_VOICE = os.environ.get("AB_VOICE") or "en-US-EmmaMultilingualNeural"
VOICE_RATE = os.environ.get("VOICE_RATE", "+6%")
VOICE_PITCH = os.environ.get("VOICE_PITCH", "+2Hz")
VIDEOS_PER_RUN = int(os.environ.get("VIDEOS_PER_RUN") or "20")   # Reels per day (private repo: ~2,000 free Actions min/month)
MAX_PRICE = float(os.environ.get("VIDEO_MAX_PRICE") or "0")   # 0 = no cap (all categories)
SKIP_WORDS = ("knife", "knives", "pocketknife", "multi-tool", "multitool", "blade", "ebook", "ps5", "xbox", "steam", "pcdd", "gog", "resale", "kindle", "watch (", "miter saw", "pex", "expander", "ryzen", "processor", "graphics card",
              "nut setter", "nut driver", "tap and die", "radial arm", "table saw", "cpu", "motherboard", "wrench set", "torque")
DEALS_FILE = Path("data/deals.json")
MADE_FILE = Path("data/videos_made.json")
OUT = Path("videos")
SITE = os.environ.get("SITE_URL", "https://momfounditcheaper.com/")

HOOKS = [
    ("Stop scrolling,", "mama."),
    ("Don't pay", "full price."),
    ("I found it", "cheaper."),
    ("Your new", "favorite find."),
]


# ---------- picking deals ----------

def price_value(p):
    try:
        return float(p.replace("$", "").replace(",", ""))
    except ValueError:
        return None


def short_title(title):
    t = re.sub(r"^(?:\[[^\]]*\]\s*|\$[\d.,]+\s*[:\-–]\s*)+", "", title)            # "[Prime] ..." / "$219.99: ..."
    t = re.sub(r"^(select accts?|select accounts|prime|amazon)\s*[:\-–]\s*", "", t, flags=re.I)
    t = re.split(r"\s+(?:for\s+)?(?:from\s+)?\$\d", t)[0]      # cut "... for $12 + free shipping"
    t = re.sub(r"^\$[\d.,]+\*?\s*/\s*", "", t)                   # "$28* / LEGO ..." -> "LEGO ..."
    t = re.sub(r"\s*\+\s*free\s+(?:s&h|shipping).*$|\s+w/\s*prime(?:\s+or\s+on)?.*$|\s+w/\s*s&s.*$", "", t, flags=re.I)
    for _ in range(4):   # peel store/price suffixes: "... Only $6 Shipped on Amazon (Reg. $199)", "... at Amazon", "... Tin Only"
        t = re.sub(r"\s*(?:\((?:reg|was|orig|list)\b[^)]*\)?|shipped on amazon|on amazon|at amazon|w/ walmart\+.*|only|just|now|for|on|at|shipped|free shipping|w/)\s*$", "", t, flags=re.I).strip(" -–,|")
    t = t.rstrip("!*.,;:- ")                                   # feed excitement marks ("Turkey Fryer!")
    if len(t) > 90:
        t = t[:90].rsplit(" ", 1)[0].rstrip(" ,-–") + "…"
    return t


PHOTOS = Path("photos")
PHOTO_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def find_photo(deal):
    """Your own (or brand-supplied) product photo from the photos/ folder.
    Match by deal id (as on the website, e.g. 3f9a1c2b7e.jpg) or by words in the file name:
    'wyze cam.jpg' matches any deal whose title has both 'wyze' and 'cam'."""
    if not PHOTOS.is_dir():
        return None
    did = hashlib.sha1(deal["id"].encode()).hexdigest()[:10]
    title = re.sub(r"[^a-z0-9]+", " ", deal["title"].lower())
    words_in_title = set(title.split())
    best = None
    for f in PHOTOS.iterdir():
        if f.suffix.lower() not in PHOTO_EXT:
            continue
        stem = f.stem.lower()
        if stem == did or (deal.get("asin") and stem == deal["asin"].lower()):
            return f
        words = [w for w in re.split(r"[^a-z0-9]+", stem) if w]
        if words and all(w in words_in_title for w in words):
            if best is None or len(words) > best[0]:     # most specific name wins
                best = (len(words), f)
    return best[1] if best else None


def _verified_amazon(d):
    import verify_link
    a = d.get("asin")
    if not a:
        return False
    try:
        meta = json.loads(Path("data/product_meta.json").read_text())
        lc = json.loads(Path("data/link_check.json").read_text())
    except Exception:
        return False
    m = meta.get(a) or {}
    if re.search(r"unavailable|out of stock|ships within \d+ to \d+ (?:month|week)|pre-?order", str(m.get("avail", "")), re.I):
        return False
    t, p = verify_link.amazon_side(a, meta, lc)
    return verify_link.check(d["title"], d.get("price", ""), t, p)[0]


try:
    _BLOCKLIST = set(json.loads(Path("data/blocklist.json").read_text()).get("asins", []))
except Exception:
    _BLOCKLIST = set()

try:
    _NO_LIFESTYLE = set(json.loads(Path("data/no_lifestyle.json").read_text()).get("asins", []))
except Exception:
    _NO_LIFESTYLE = set()                         # ASINs whose gallery is all packaging/spec panels: post+pin only, no Reel


def pick_deals(deals, made):
    good = []
    for d in deals:
        if qa_check(d)[0] or d.get("asin") in _BLOCKLIST:
            continue                                  # quality gate + owner blocklist: never a Reel
        price = price_value(d.get("price", ""))
        low = d["title"].lower()
        if d["id"] in made or price is None or (MAX_PRICE and price > MAX_PRICE) or price < 1:
            continue
        if any(w in low for w in SKIP_WORDS):
            continue
        if not _verified_amazon(d):
            continue                                  # only Amazon-verified deals get a video (site lists only those)
        if AMAZON_PRICES != "hide":
            import time as _t
            _m = json.loads(Path("data/product_meta.json").read_text()).get(d.get("asin", ""), {}) if Path("data/product_meta.json").exists() else {}
            _n = price_value(str(_m.get("now") or ""))
            if not _n or not _m.get("checked") or _t.time() - _m["checked"] > 36 * 3600 or abs(_n - price) / _n > 0.05:
                continue                              # a shown price must be Amazon's own, read in the last 36h
            _l = price_value(str(_m.get("list") or "")) if _m.get("list") else None
            _real_deal = (_l and _n < _l * 0.9) or (d.get("code") and d["code"] != "w/ code") or d.get("coupon") or is_lowest_seen(d)
            if not _real_deal:
                continue                              # price == list and no coupon: nothing "cheaper" to show
        if not lifestyle_photo(d):
            continue                                  # no in-use photo = frame 1 would be a white-bg hero; skip the video (post/pin still run)
        score = (2 if d.get("code") and d["code"] != "w/ code" else 0) + (1 if d.get("coupon") else 0)
        score += 3 if find_photo(d) else 0          # deals with a real photo go first
        score += 2 * len(viral_sources(d, SIGNALS))  # buzzing in several places = viral
        good.append((score, d["seen"], d))
    good.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [d for _, _, d in good[:VIDEOS_PER_RUN]]


# ---------- drawing scenes (elegant editorial look) ----------
# Ivory paper, deep charcoal, champagne gold. Playfair Display headlines,
# Inter for small caps labels. Thin gold rules instead of boxes.

from brand import CREAM as IVORY, INK as CHAR, TANGERINE as GOLD, MUTED, PEACH as BLUSH, YELLOW   # brand tokens (v2)
FONTS = Path(__file__).parent / "fonts"


WEIGHTS = {"Regular": 400, "Medium": 500, "SemiBold": 600, "Bold": 700, "ExtraBold": 800, "Black": 900}


def _variable(file, size, weight):
    """Open a variable font at a numeric weight (works for italic files too)."""
    f = ImageFont.truetype(str(FONTS / file), size)
    axes = []
    for ax in f.get_variation_axes():
        name = ax["name"].lower() if isinstance(ax["name"], str) else ax["name"].decode().lower()
        axes.append(WEIGHTS[weight] if "weight" in name else (min(max(32, ax["minimum"]), ax["maximum"]) if "optical" in name else ax["default"]))
    f.set_variation_by_axes(axes)
    return f


def serif(size, weight="Bold", italic=False):
    return _variable("PlayfairDisplay-Italic.ttf" if italic else "PlayfairDisplay.ttf", size, weight)


def sans(size, weight="Medium"):
    return _variable("Inter.ttf", size, weight)


def wrap(draw, text, fnt, max_w):
    words, lines, line = text.split(), [], ""
    for w in words:
        test = f"{line} {w}".strip()
        if draw.textlength(test, font=fnt) <= max_w:
            line = test
        else:
            lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


def centered(draw, y, text, fnt, fill, max_w=W - 200, gap=14, spacing=0):
    for line in wrap(draw, text, fnt, max_w):
        if spacing:  # letter-spaced small caps
            w = sum(draw.textlength(c, font=fnt) for c in line) + spacing * (len(line) - 1)
            x = (W - w) / 2
            for c in line:
                draw.text((x, y), c, font=fnt, fill=fill)
                x += draw.textlength(c, font=fnt) + spacing
        else:
            w = draw.textlength(line, font=fnt)
            draw.text(((W - w) / 2, y), line, font=fnt, fill=fill)
        y += fnt.size + gap
    return y


def fit(draw, text, maker, start, max_w, max_lines=3, min_size=56):
    """Largest font that wraps `text` into max_lines inside max_w."""
    size = start
    while size > min_size:
        f = maker(size)
        if len(wrap(draw, text, f, max_w)) <= max_lines:
            return f
        size -= 6
    return maker(min_size)


def rule(draw, y, w=220, color=GOLD):
    draw.line([((W - w) / 2, y), ((W + w) / 2, y)], fill=color, width=3)


SAFE_TOP, SAFE_BOTTOM = 350, 1400      # Shorts UI covers top 15 % / bottom 25 %; margins absorb the 1.10x zoom (y=350 -> 289 px)


def masthead(draw, color, y=SAFE_TOP + 12):
    """Small brand line, right-aligned on the same row as the #AD pill (both inside the safe zone)."""
    f = sans(24, "SemiBold")
    txt = BRAND.upper()
    w = sum(draw.textlength(c, font=f) for c in txt) + 4 * (len(txt) - 1)
    x = W - 56 - w
    for c in txt:
        draw.text((x, y), c, font=f, fill=color)
        x += draw.textlength(c, font=f) + 4


def footer(draw, color=None, dark_bg=True):
    """Disclosure pill, top-left, first row of the safe zone (readable on any background, clear of Reels/Shorts UI)."""
    f = sans(28, "Bold")
    txt = "#AD · PAID LINK · PRICES CAN CHANGE"
    w = draw.textlength(txt, font=f)
    x0, y0 = 56, SAFE_TOP
    fill, ink = ((31, 26, 46), IVORY) if dark_bg else (IVORY, CHAR)
    draw.rounded_rectangle([x0, y0, x0 + w + 40, y0 + 50], radius=25, fill=fill, outline=GOLD, width=2)
    draw.text((x0 + 20, y0 + 9), txt, font=f, fill=ink)


def badge_text(deal):
    """Only real signals from the deal itself - never invented."""
    if deal.get("new"):
        return "NEW RELEASE"
    if deal.get("bestseller"):
        return "BEST SELLER"
    t = deal.get("thumbs", 0)
    if t >= 30:
        return f"POPULAR ON DEAL SITES  ·  +{t} VOTES"
    if t >= 10:
        return f"TRENDING ON DEAL SITES  ·  +{t} VOTES"
    return "TODAY'S FIND"


def _scene_score(path):
    """How much a gallery photo looks like a real scene (product in use / worn) rather than a studio
    cut-out or a seller infographic. Returns (non_white_border, dominant_color_share)."""
    im = Image.open(path).convert("RGB").resize((120, 120))
    px = im.load()
    border = tot = 0
    for x in range(120):
        for y in range(120):
            if x < 8 or y < 8 or x >= 112 or y >= 112:
                tot += 1
                if min(px[x, y]) > 235:
                    border += 1
    q = im.quantize(colors=16)
    counts = sorted(q.getcolors(), reverse=True)
    flat = 0                                  # flat band top/bottom = seller caption strip / infographic header
    for strip in (q.crop((0, 0, 120, 18)), q.crop((0, 102, 120, 120))):
        c = sorted(strip.getcolors(), reverse=True)
        flat = max(flat, c[0][0] / (120 * 18))
    return 1 - border / tot, max(counts[0][0] / (120 * 120), flat * 0.5)


def lifestyle_photo(deal):
    """Best in-use / lifestyle shot from Amazon's own gallery (photos/<ASIN>_2..5.jpg), or None.
    Rejects studio cut-outs (mostly-white). An ASIN tagged in data/no_lifestyle.json (a human/QA call that
    its gallery is all packaging or spec panels) returns None, so that product is a post/pin, never a Reel."""
    asin = deal.get("asin")
    if not asin or asin in _NO_LIFESTYLE:
        return None
    best, best_s = None, 0
    for n in range(2, 6):
        p = PHOTOS / f"{asin}_{n}.jpg"
        if not p.is_file():
            continue
        try:
            nonwhite, dom = _scene_score(p)
        except Exception:
            continue
        if nonwhite >= 0.6 and dom <= 0.25 and nonwhite - dom > best_s:
            best, best_s = p, nonwhite - dom
    return best


def scene_hook(path, hook, photo=None, studio=None):
    """Frame 1: the product in use (full-bleed real photo) with the hook in a bold block, top-centre of the
    safe zone. No in-use shot: the studio photo on a blurred fill (never a text-only first frame)."""
    from PIL import ImageFilter, ImageOps
    if photo or studio:
        try:
            src = Image.open(photo or studio).convert("RGB")
            # seller caption strips (flat colour band top/bottom) are cropped away before the full-bleed fit
            q = src.resize((120, 120)).quantize(colors=16)
            sw, sh = src.size
            for strip, box in ((q.crop((0, 0, 120, 18)), (0, int(sh * 0.2), sw, sh)), (q.crop((0, 102, 120, 120)), (0, 0, sw, int(sh * 0.8)))):
                if sorted(strip.getcolors(), reverse=True)[0][0] / (120 * 18) >= 0.45:
                    src = src.crop(box)
                    sw, sh = src.size
            if photo and min(W / sw, H / sh) <= 2.2:
                img = ImageOps.fit(src, (W, H), Image.LANCZOS, centering=(0.5, 0.45))
            else:                                           # small or studio photo: fill the lower frame on a blurred bed
                img = ImageOps.fit(src, (W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(55))
                img = Image.blend(img, Image.new("RGB", (W, H), CHAR), 0.4)
                band_top, band_h = 740, H - 740 - 40         # product sits big in the space below the headline
                scale = min(2.2, (W - 80) / sw, band_h / sh)
                pic = src.resize((int(sw * scale), int(sh * scale)), Image.LANCZOS)
                img.paste(pic, ((W - pic.width) // 2, band_top + (band_h - pic.height) // 2))
            shade = Image.new("L", (W, H), 0)                     # soft darkening behind the headline
            ImageDraw.Draw(shade).rectangle([0, 0, W, 760], fill=120)
            img.paste((20, 16, 30), mask=shade.filter(ImageFilter.GaussianBlur(90)))
            d = ImageDraw.Draw(img)
            f1 = fit(d, hook[0], lambda s: sans(s, "Bold"), 80, W - 260, max_lines=1, min_size=52)
            f2 = fit(d, hook[1], lambda s: sans(s, "ExtraBold"), 104, W - 260, max_lines=1, min_size=60)
            w1, w2 = d.textlength(hook[0], font=f1), d.textlength(hook[1], font=f2)
            bw = min(max(w1, w2) + 120, W - 120)
            y0 = 440
            d.rounded_rectangle([(W - bw) / 2, y0, (W + bw) / 2, y0 + f1.size + f2.size + 90], 28, fill=(255, 197, 61))
            d.text(((W - w1) / 2, y0 + 28), hook[0], font=f1, fill=(31, 26, 46))
            d.text(((W - w2) / 2, y0 + 28 + f1.size + 14), hook[1], font=f2, fill=(31, 26, 46))
            footer(d, MUTED)
            img.save(path)
            return
        except Exception as e:
            print(f"[warn] hook photo {photo}: {e}")
    img = Image.new("RGB", (W, H), IVORY)
    d = ImageDraw.Draw(img)
    masthead(d, CHAR)
    centered(d, 640, hook[0], serif(120, "Regular", italic=True), CHAR)
    centered(d, 800, hook[1], serif(150, "Bold"), CHAR)
    rule(d, 1040, 160)
    centered(d, 1090, "TODAY'S FIND", sans(36, "SemiBold"), MUTED, spacing=8)
    footer(d, MUTED)
    img.save(path)


def scene_product_photo(path, title, deal, photo, price="", was_label="", was=""):
    """Photo on an ivory card: soft shadow, gold frame, badge above, name below."""
    from PIL import ImageFilter, ImageOps
    img = Image.new("RGB", (W, H), CHAR)
    # blurred, darkened photo fills the background
    src = Image.open(photo).convert("RGB")
    bg = ImageOps.fit(src, (W, H)).filter(ImageFilter.GaussianBlur(40))
    img = Image.blend(bg, img, 0.72)
    d = ImageDraw.Draw(img)
    masthead(d, IVORY)
    badge = badge_text(deal)
    bf = sans(30, "SemiBold")
    bw = sum(d.textlength(c, font=bf) for c in badge) + 6 * (len(badge) - 1) + 80
    d.rounded_rectangle([(W - bw) / 2, 390, (W + bw) / 2, 466], radius=38, fill=CHAR, outline=GOLD, width=3)
    centered(d, 409, badge, bf, GOLD, spacing=6)
    # card with the product photo, whole product visible (no cropping); everything ends above SAFE_BOTTOM
    cw, ch, top = (860, 560, 500) if price else (860, 720, 500)     # room under the card for the price chip
    shadow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(shadow).rounded_rectangle([(W - cw) / 2 + 10, top + 24, (W + cw) / 2 + 10, top + ch + 24], 48, fill=150)
    img.paste((0, 0, 0), mask=shadow.filter(ImageFilter.GaussianBlur(28)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([(W - cw) / 2, top, (W + cw) / 2, top + ch], 48, fill=(255, 255, 255), outline=GOLD, width=4)
    pic = ImageOps.contain(src, (cw - 90, ch - 90))
    img.paste(pic, ((W - pic.width) // 2, top + (ch - pic.height) // 2))
    d = ImageDraw.Draw(img)
    if price and len(title) > 60:                       # keep the variant/bundle; trim only a very long tail at a boundary
        title = re.split(r"\s[-–|]\s|,\s(?=[A-Z])", title)[0]
    tf = fit(d, title, lambda s: serif(s, "SemiBold"), 72 if price else 84, W - 180, max_lines=2, min_size=38)
    y = centered(d, top + ch + 36, title, tf, IVORY, gap=12, max_w=W - 180)
    if price:
        price_chip(img, price, was_label, was, min(y + 22, SAFE_BOTTOM - 180))
    else:
        rule(d, y + 40, 160)
    footer(ImageDraw.Draw(img), MUTED)
    img.save(path)


def scene_product(path, title, deal, price="", was_label="", was=""):
    photo = find_photo(deal)        # deal-feed photos stay on (Rohini 2026-11-25)
    if photo:
        try:
            return scene_product_photo(path, title, deal, photo, price, was_label, was)
        except Exception as e:      # unreadable image: fall back to the text card
            print(f"[warn] photo {photo}: {e}")
    img = Image.new("RGB", (W, H), CHAR)
    d = ImageDraw.Draw(img)
    masthead(d, IVORY)
    badge = badge_text(deal)
    bf = sans(32, "SemiBold")
    bw = sum(d.textlength(c, font=bf) for c in badge) + 6 * (len(badge) - 1) + 80
    d.rounded_rectangle([(W - bw) / 2, 440, (W + bw) / 2, 520], radius=40, outline=GOLD, width=3)
    centered(d, 460, badge, bf, GOLD, spacing=6)
    tf = fit(d, title, lambda s: serif(s, "SemiBold"), 112, W - 200, max_lines=3)
    y = centered(d, 600, title, tf, IVORY, gap=18)
    rule(d, y + 50, 160)
    if price:
        price_chip(img, price, was_label, was, y + 110)
    footer(ImageDraw.Draw(img), MUTED)
    img.save(path)


def scene_features(path, features, title="Why it's a good find"):
    img = Image.new("RGB", (W, H), IVORY)
    d = ImageDraw.Draw(img)
    masthead(d, CHAR)
    centered(d, 420, title, serif(96, "Regular", italic=True), CHAR)
    rule(d, 570, 160)
    y = 660
    for i, feat in enumerate(features[:3], 1):
        centered(d, y, f"0{i}", serif(56, "Bold"), GOLD)
        y = centered(d, y + 80, feat, sans(50, "Medium"), CHAR, max_w=W - 240, gap=10) + 50
    footer(d, MUTED)
    img.save(path)


def scene_price(path, price, was, code, coupon, amazon=False, stamp="", pct=0, lowest=""):
    """Price card: struck reference price, big price, the % OFF (spoken here, so shown big here), lowest-seen line."""
    img = Image.new("RGB", (W, H), CHAR)
    d = ImageDraw.Draw(img)
    masthead(d, IVORY)
    _a, _b = price_value(price or ""), price_value(was or "")
    if not pct and _a and _b and _b > _a * 1.1:
        pct = int(round(100 * (_b - _a) / _b))
    y = 440
    if amazon:      # Amazon policy: no price unless it comes from Amazon's API
        y = centered(d, y + 160, "PRICE DROP", sans(44, "SemiBold"), MUTED, spacing=10) + 40
        y = centered(d, y, "on Amazon today", serif(110, "Bold"), GOLD) + 50
        y = centered(d, y, "Tap the link for today's price", serif(58, "Regular", italic=True), IVORY) + 110
    elif was:
        wf = serif(72, "Regular")
        label = was if was.lower().startswith(("list", "was")) else f"was {was}"
        w = d.textlength(label, font=wf)
        d.text(((W - w) / 2, y), label, font=wf, fill=(214, 206, 222))                              # readable on navy
        d.line([((W - w) / 2 - 10, y + 44), ((W + w) / 2 + 10, y + 44)], fill=BLUSH, width=6)   # through the digits
        y += 110
    else:
        y = centered(d, y, "NOW ONLY", sans(40, "SemiBold"), MUTED, spacing=8) + 30
    if not amazon:
        pf = fit(d, price, lambda s: serif(s, "Bold"), 260, W - 200, max_lines=1, min_size=120)
        y = centered(d, y, price, pf, GOLD) + 90                     # clear of the "$" descender
        if stamp:
            y = centered(d, y, stamp, sans(28, "Medium"), (214, 206, 222), spacing=2) + 70
        if pct >= 10:                                              # big, in the space that used to be empty
            sf = sans(150, "ExtraBold")
            txt = f"{pct}% OFF"
            tw = d.textlength(txt, font=sf)
            d.rounded_rectangle([(W - tw) / 2 - 50, y, (W + tw) / 2 + 50, y + 190], radius=36, fill=(255, 197, 61))
            d.text(((W - tw) / 2, y + 8), txt, font=sf, fill=(31, 26, 46))
            y += 230
        if lowest:
            y = centered(d, y, lowest, sans(40, "SemiBold"), IVORY, spacing=2) + 70
    if code and code != "w/ code":
        y = min(y, SAFE_BOTTOM - 220)
        centered(d, y, "WITH CODE", sans(34, "SemiBold"), MUTED, spacing=8)
        cf = sans(80, "Bold")
        cw = sum(d.textlength(c, font=cf) for c in code) + 10 * (len(code) - 1)
        d.rounded_rectangle([(W - cw) / 2 - 60, y + 70, (W + cw) / 2 + 60, y + 210], radius=16, outline=GOLD, width=3)
        centered(d, y + 95, code, cf, IVORY, spacing=10)
    elif coupon or code:
        centered(d, min(y, SAFE_BOTTOM - 80), "CLIP THE COUPON" if coupon else "PROMO CODE INSIDE", sans(48, "SemiBold"), IVORY, spacing=8)
    footer(d, MUTED)
    img.save(path)


def scene_cta(path):
    img = Image.new("RGB", (W, H), IVORY)
    d = ImageDraw.Draw(img)
    centered(d, 460, "Tap the link in the caption", serif(76, "Regular", italic=True), CHAR)
    centered(d, 580, "for today's price", serif(76, "Regular", italic=True), CHAR)
    rule(d, 750, 160)
    centered(d, 820, "Mom Found", serif(150, "Bold"), CHAR)
    centered(d, 990, "It Cheaper", serif(150, "Bold"), GOLD)
    rule(d, 1210, 160)
    centered(d, 1260, "JOIN FREE  ·  NEW DEALS DAILY", sans(34, "SemiBold"), MUTED, spacing=7)
    footer(d, MUTED)
    img.save(path)


# ---------- voice and video (one clip per scene, scene length = its own line) ----------

FPS = 30
LEAD, TAIL = 0.15, 0.10          # speech starts just after the dissolve; short breath before the next scene (dead air < 0.6 s)
MIN_SCENE = 1.6                  # shorter than this the zoom is invisible
MAX_SCENE = 6.0                  # benchmark: no single picture held longer than this
MIN_GALLERY = 2.2                # a photo + caption needs this long to read
MIN_TOTAL = 16.0                 # benchmark band 16-32 s: keep extra gallery looks until we reach it
MAX_TOTAL = 24.0                 # Reels/Shorts sweet spot; gallery/features trimmed to fit


def _grid(t):
    """Round a duration up to the frame grid so xfade offsets never pass the end of an input."""
    import math
    return math.ceil(t * FPS) / FPS


async def _edge_clip(text, mp3, voice, rate, pitch):
    import edge_tts
    await edge_tts.Communicate(text, voice or VOICE, rate=rate, pitch=pitch).save(str(mp3))


def tts_clip(text, wav, voice, rate=None, pitch=None):
    """One spoken line -> trimmed 24 kHz mono WAV. Returns its exact duration (seconds, by samples).
    ElevenLabs when ELEVENLABS_API_KEY is set (one request per line so each scene can be timed), else Edge."""
    wav = Path(wav)
    mp3 = wav.with_suffix(".mp3")
    key = os.environ.get("ELEVENLABS_API_KEY", "")
    if key:
        import urllib.request
        vid = os.environ.get("ELEVENLABS_VOICE_ID") or "21m00Tcm4TlvDq8ikWAM"
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{vid}",
            data=json.dumps({"text": text, "model_id": "eleven_multilingual_v2",
                             "voice_settings": {"stability": 0.35, "similarity_boost": 0.8, "style": 0.55}}).encode(),
            headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
        with urllib.request.urlopen(req, timeout=60) as r:
            mp3.write_bytes(r.read())
    else:
        asyncio.run(_edge_clip(text, mp3, voice, rate or VOICE_RATE, pitch or VOICE_PITCH))
    # trim the lead/trail silence Edge adds, normalise format; measure by samples (mp3 headers are estimates)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-af",
                    "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,"
                    "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08,areverse,"
                    "aresample=24000,aformat=channel_layouts=mono", str(wav)], check=True)
    import wave
    with wave.open(str(wav)) as w:                       # exact length by sample count (mp3 headers are estimates)
        return w.getnframes() / float(w.getframerate())


def build_audio(clips, scene_durs, out_path):
    """clips: WAV per scene (or None). Each is delayed by LEAD and padded to its scene length, then joined:
    the audio is sum(scene_durs) long by construction, so speech never drifts from its scene."""
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    labels = []
    for i, (c, d) in enumerate(zip(clips, scene_durs)):
        if c:
            cmd += ["-i", str(c)]
        else:
            cmd += ["-f", "lavfi", "-t", f"{d:.3f}", "-i", "anullsrc=r=24000:cl=mono"]
        labels.append(f"[{i}:a]adelay={int(LEAD * 1000)}:all=1,apad=whole_dur={d:.3f},atrim=0:{d:.3f}[a{i}]")
    joined = "".join(f"[a{i}]" for i in range(len(clips)))
    # loudnorm to -14 LUFS / -1.5 dBTP: Shorts-level loudness, no clipping; the dur=sum(scene_durs) stays exact
    cmd += ["-filter_complex", ";".join(labels) + f";{joined}concat=n={len(clips)}:v=0:a=1,"
            f"loudnorm=I=-14:TP=-1.5:LRA=11,atrim=0:{sum(scene_durs):.3f},apad=whole_dur={sum(scene_durs):.3f}[out]",
            "-map", "[out]", "-c:a", "aac", "-b:a", "128k", str(out_path)]
    subprocess.run(cmd, check=True)


def render(scenes, durations, audio, out_path, zooms=None):
    """Steady Ken Burns on each scene (zoom in, or zoom out on alternate gallery shots), 0.4 s dissolve, voice on top."""
    fade = 0.25                      # short dissolve: two caption layers never read at once
    zooms = zooms or ["in"] * len(scenes)
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for s in scenes:
        cmd += ["-i", str(s)]
    if audio:
        cmd += ["-i", str(audio)]
    parts = []
    for i, (dur, zd) in enumerate(zip(durations, zooms)):
        frames = int(round((dur + fade) * FPS))
        z = {"in": "min(1+0.0004*on,1.04)", "out": "max(1.04-0.0004*on,1.0)",
             "push": "min(1+0.0012*on,1.10)"}[zd]           # push = frame-1 photo, visibly alive in the first second
        parts.append(f"[{i}:v]scale={W*2}:{H*2}:flags=lanczos,zoompan=z='{z}':d={frames}"
                     f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS},setsar=1[v{i}]")
    last, offset = "v0", 0.0
    for i in range(1, len(durations)):
        offset += durations[i - 1]
        parts.append(f"[{last}][v{i}]xfade=transition=fade:duration={fade}:offset={offset:.3f}[x{i}]")
        last = f"x{i}"
    cmd += ["-filter_complex", ";".join(parts), "-map", f"[{last}]"]
    if audio:
        cmd += ["-map", f"{len(durations)}:a", "-c:a", "copy", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(out_path)]
    subprocess.run(cmd, check=True)


def _ghash(path):
    """8x8 difference hash, for dropping near-duplicate gallery shots."""
    im = Image.open(path).convert("L").resize((9, 8))
    px = im.load()
    return tuple(px[x + 1, y] > px[x, y] for y in range(8) for x in range(8))


def gallery_photos(deal, limit=3):
    """Extra product photos saved by the Lenovo run: photos/<ASIN>_2.jpg ... (hero is <ASIN>.jpg).
    Near-duplicate angles are dropped so 'from another angle' is never the same shot twice."""
    a = deal.get("asin")
    if not a or not PHOTOS.is_dir():
        return []
    out, hashes = [], []
    for i in range(2, 2 + limit + 3):
        for ext in (".jpg", ".png", ".webp"):
            f = PHOTOS / f"{a}_{i}{ext}"
            if f.exists():
                try:
                    h = _ghash(f)
                    if any(sum(x != y for x, y in zip(h, g)) <= 6 for g in hashes):
                        break                               # too close to a shot we already kept
                    hashes.append(h)
                except Exception:
                    pass
                out.append(f)
                break
    return out[:limit]


def was_info(deal):
    """(label, value) for the reference price, from ONE source so screen and voice agree:
    Amazon's list price when the Lenovo read one that makes sense, else the deal's own 'was'."""
    now = price_value(deal.get("price", "") or "") or 0
    m = {}
    try:
        m = json.loads(Path("data/product_meta.json").read_text()).get(deal.get("asin", "")) or {}
    except Exception:
        pass
    lst = price_value(str(m.get("list") or "")) if m.get("list") else None
    if lst and now and now < lst <= 6 * now:
        return "List price", m["list"]
    w = deal.get("was", "")
    wv = price_value(w) if w else None
    if wv and now and now < wv <= 6 * now:
        return "Was", w
    return "", ""


def scene_gallery(path, photo, caption_text, idx):
    """One extra product photo, big, with the feature it illustrates underneath."""
    from PIL import ImageFilter, ImageOps
    src = Image.open(photo).convert("RGB")
    img = Image.new("RGB", (W, H), CHAR)
    bg = ImageOps.fit(src, (W, H)).filter(ImageFilter.GaussianBlur(40))
    img = Image.blend(bg, img, 0.72)
    d = ImageDraw.Draw(img)
    masthead(d, IVORY)
    cw, ch, top = 900, 760, 400
    shadow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(shadow).rounded_rectangle([(W - cw) / 2 + 10, top + 24, (W + cw) / 2 + 10, top + ch + 24], 48, fill=150)
    img.paste((0, 0, 0), mask=shadow.filter(ImageFilter.GaussianBlur(28)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([(W - cw) / 2, top, (W + cw) / 2, top + ch], 48, fill=(255, 255, 255), outline=GOLD, width=4)
    pic = ImageOps.contain(src, (cw - 80, ch - 80))
    img.paste(pic, ((W - pic.width) // 2, top + (ch - pic.height) // 2))
    d = ImageDraw.Draw(img)
    centered(d, top + ch + 44, f"0{idx}", serif(52, "Bold"), GOLD)
    cf = fit(d, caption_text, lambda s_: sans(s_, "Medium"), 54, W - 200, max_lines=2, min_size=40)
    centered(d, top + ch + 116, caption_text, cf, IVORY, gap=10)            # ends above SAFE_BOTTOM
    footer(d, MUTED)
    img.save(path)


def price_chip(img, price, was_label, was_val, y0=1200):
    """Gold price pill on the product card (price is spoken on this scene, so it must be seen here too)."""
    d = ImageDraw.Draw(img)
    pf = serif(76, "Bold")
    w = d.textlength(price, font=pf)
    x0 = (W - w) / 2 - 44
    y0 = min(y0, SAFE_BOTTOM - 180)                      # pill + was-line stay above the Shorts UI
    d.rounded_rectangle([x0, y0, x0 + w + 88, y0 + 110], radius=24, fill=GOLD)
    d.text((x0 + 44, y0 + 10), price, font=pf, fill=IVORY)
    if was_val:
        wf = sans(40, "SemiBold")
        lbl = f"{was_label} {was_val}"
        lw = d.textlength(lbl, font=wf)
        d.text(((W - lw) / 2, y0 + 126), lbl, font=wf, fill=IVORY)
        d.line([((W - lw) / 2 - 4, y0 + 152), ((W + lw) / 2 + 4, y0 + 152)], fill=BLUSH, width=4)


def under_band(p):
    """'under $25' with the smallest true band (strict <), or ''."""
    for t in (5, 10, 15, 20, 25, 30, 40, 50, 75, 100, 150, 200, 300, 500):
        if p < t:
            return f"under ${t}"
    return ""


def caption(title, price, code, coupon, deal=None, cat="", was="", pct=0):
    extra = f" Use code {code}." if code and code != "w/ code" else (" Clip the coupon!" if coupon else "")
    if deal and is_amazon(deal) and AMAZON_PRICES != "hide":
        # title formula from the trend benchmark: <category> find under $X that's actually worth it
        band = under_band(price_value(price) or 0)
        noun = {"Baby & Kids": "mom find", "Toys & Games": "toy find", "Beauty & Health": "beauty find",
                "Home & Kitchen": "kitchen find", "Fashion": "closet find", "Tech & Electronics": "gadget find",
                "Pets": "pet find", "Holiday & Seasonal": "holiday find"}.get(cat, "Amazon find")
        lead = f"#ad {noun.capitalize()} {band} that's actually worth it \U0001F440\n" if band else "#ad Actually worth it \U0001F440\n"
        wasbit = f", list {was}, {pct}% off" if was and pct >= 10 else ""
        head = (f"{lead}{title} - {price} on Amazon "
                f"(price as of {as_of(deal['seen'])}{wasbit}; prices change).{extra}")
    elif deal and is_amazon(deal):    # no price for Amazon items (Associates policy)
        head = f"#ad Mom found it cheaper! Price drop on Amazon: {title}. Tap for today's price.{extra}"
    else:
        head = f"#ad Mom found it cheaper! {title} - now just {price}.{extra}"
    return (f"{head}\n\n"
            f"Get it here: {SITE}#d-{hashlib.sha1(deal['id'].encode()).hexdigest()[:10] if deal else ''}\n"
            f"More deals daily in our free Facebook group: {BRAND}\n\n"
            "#amazonfinds #momfinds #dealsforyou #founditcheaper #savemoney\n"
            "As an Amazon Associate I earn from qualifying purchases. Prices and codes can change.")


def is_lowest_seen(deal):
    """True only when our own price history has 2+ points and today's price is the lowest."""
    hist_file = Path("data/price_history.json")
    m = re.search(r"\$\s?([\d,]+(?:\.\d{1,2})?)", deal.get("price", "") or "")
    if not (hist_file.exists() and m):
        return False
    from deal_finder import product_key
    price = float(m.group(1).replace(",", ""))
    day = (deal.get("seen") or "")[:10]
    # earlier sightings only (not today's own entry); today's price must beat all of them
    earlier = [p for d, p in json.loads(hist_file.read_text()).get(product_key(deal), []) if d != day]
    return len(earlier) >= 1 and price < min(earlier)



_LAST_HOOK = [None]
_USED_HOOKS = set()           # hooks already used this run, so no two videos open the same way


def spoken_name(title):
    """Short product name for the voice: cut at a natural break, never on a dangling word or bare number."""
    t = re.split(r"\s[-–|]\s|:\s|\(", title)[0]
    words = t.split()
    cut = {"with", "for", "of", "to", "in", "on", "by", "w/", "plus", "or", "featuring", "includes"}
    if len(words) > 8:
        idx = [i for i, w in enumerate(words[:11]) if w.lower() in cut and i >= 3]
        words = words[:idx[0]] if idx and idx[0] >= 4 else (words[:idx[-1]] if idx else words[:11])
    stop = {"with", "and", "&", "for", "of", "the", "a", "to", "in", "on", "by", "w/", "plus", "or"}
    while len(words) > 2 and (words[-1].lower().strip(",.") in stop or re.fullmatch(r"[\d.,]+[a-z]*", words[-1].lower())):
        words.pop()
    return " ".join(words).rstrip(".!?,;: -")


def _short_feats(feats, n):
    out = []
    for f in feats:
        f = re.sub(r"\s+", " ", str(f)).strip(" .;:-")
        if 12 <= len(f) <= 70 and not re.search(r"https?://|\$\d", f):
            out.append(f[0].upper() + f[1:])
        if len(out) >= n:
            break
    return out


def make_one(n, deal, work):
    hide = is_amazon(deal) and AMAZON_PRICES == "hide"
    stamp = f"Amazon price as of {as_of(deal['seen'])}" if is_amazon(deal) and not hide else ""
    title = short_title(no_price_title(deal["title"]) if hide else deal["title"])
    try:                                                     # Amazon's own title wins (right variant, no feed residue)
        import build_site as _bs
        _at = _bs._amz_title(deal)
        if _at and len(_at.split()) >= 3:
            title = _at
    except Exception:
        pass
    price, code, coupon = deal["price"], deal.get("code", ""), deal.get("coupon", "")
    meta = {}
    try:
        meta = json.loads(Path("data/product_meta.json").read_text()).get(deal.get("asin", "")) or {}
    except Exception:
        pass
    if code and code.lower() not in str(meta.get("promo", "")).lower():
        code = ""          # a code only if Amazon's own page showed it; never from a deal feed alone
    was_label, was = ("", "") if hide else was_info(deal)
    pct = 0
    if was:
        a, b = price_value(price), price_value(was)
        pct = int(round(100 * (b - a) / b)) if a and b and b > a else 0
    title = title.replace("\u2122", "").replace("\u00ae", "").strip()
    spoken = spoken_name(title)
    try:
        from deal_finder import category_of
        _cat = category_of(str(meta.get("title") or deal["title"])) or deal.get("category", "")
    except Exception:
        _cat = deal.get("category", "")
    hook = hook_for(_cat, deal["id"], avoid=_LAST_HOOK[0], used=_USED_HOOKS, title=title)
    _USED_HOOKS.add(hook)
    _pv = price_value(price) or 0
    if _pv > 50 and "small price" in " ".join(hook).lower():
        hook = ("Don't pay", "full price.")
    _LAST_HOOK[0] = hook
    gallery = [] if hide else gallery_photos(deal)
    feats_all = _short_feats(deal.get("features") or [], 3)
    clean_code = "".join(c for c in (code or "").upper() if c.isalnum())
    has_code = bool(clean_code) and code != "w/ code"
    lowest = (not hide) and is_lowest_seen(deal)

    # ---- scenes, each with the exact line spoken over it ----
    plan = []    # (name, draw_fn, args, spoken, rate, pitch, zoom)
    life = None if hide else lifestyle_photo(deal)          # frame 1 = product in use when Amazon's gallery has one
    plan.append(("hook", scene_hook, (hook, life, find_photo(deal)), f"{hook[0]} {hook[1]}", "+12%", "+4Hz", "push"))
    if hide:
        plan.append(("product", scene_product, (title, deal), f"{spoken} just had a price drop on Amazon.", None, None, "in"))
    else:
        # short line here (scene <= MAX_SCENE); the list price and % move to the price card where they are shown big
        line = f"{spoken} is only {price} right now."
        plan.append(("product", scene_product, (title, deal, price, was_label, was), line, None, None, "in"))
    if gallery and life and life in gallery and len(gallery) > 1:
        gallery = [g for g in gallery if g != life]          # already used as frame 1
    if gallery:
        fillers = ["Here's a closer look at what you get.", "And here it is from another angle.", "One more look before you decide."]
        try:
            _r, _n = float(meta.get("rating") or 0), int(meta.get("reviews") or 0)
        except Exception:
            _r, _n = 0, 0
        proof = f"Rated {_r:g} stars by {_n:,} shoppers on Amazon." if _r >= 4.3 and _n >= 25 else ""
        lines = list(feats_all)
        if proof:
            lines.insert(min(1, len(lines)), proof)
        # real lines first; extra looks with short fillers keep the video inside the 16-32 s band
        gallery = gallery[:max(len(lines), 2)] if lines else gallery[:2]
        for i, g in enumerate(gallery):
            line = lines[i] if i < len(lines) else fillers[min(i, len(fillers) - 1)]
            plan.append((f"gallery{i+1}", scene_gallery, (g, line, i + 1), line, None, None, "out" if i % 2 == 0 else "in"))
        rest = feats_all[len(gallery):]
    else:
        rest = feats_all
    if rest:
        plan.append(("features", scene_features, (rest, pick(FEATURES_TITLES, deal["id"], "ft")), " ".join(f + "." for f in rest), None, None, "in"))
    if hide:
        plan.append(("price", scene_price, ("", "", code, coupon, True, ""), "Tap the link for today's price." + (f" Use code {', '.join(clean_code)}." if has_code else " Just clip the coupon." if coupon else ""), None, None, "in"))
    else:
        bits = []
        if pct >= 10 and was_label == "List price":
            bits.append(f"Down from a {was} list price, that's {pct} percent off.")
        elif pct >= 10:
            bits.append(f"It was {was}. That's {pct} percent off.")
        elif was:
            bits.append(f"Down from {was}.")
        if lowest:
            bits.append("The lowest price we've tracked on it.")
        if has_code:
            bits.append(f"Use code {', '.join(clean_code)}.")
        elif coupon:
            bits.append("Just clip the coupon.")
        if not bits:
            bits.append(f"Only {price} on Amazon right now.")
        plan.append(("price", scene_price, (price, f"{was_label.lower()} {was}" if was else "", code, coupon, False, stamp, pct,
                                            "LOWEST PRICE WE'VE TRACKED" if lowest else ""), " ".join(bits), None, None, "in"))
    plan.append(("cta", scene_cta, (), pick(CLOSERS, deal["id"], "cl").format(brand=BRAND).split(". ")[0].rstrip(".") + ".", None, None, "in"))

    # ---- voice: one clip per scene; scene lasts exactly as long as its line ----
    ab = AB_VOICE.lower() != "off" and int(hashlib.sha1(deal["id"].encode()).hexdigest(), 16) % 2 == 1
    voice = AB_VOICE if ab else VOICE
    clips, durs, scenes, zooms, names, speech = [], [], [], [], [], []
    for i, (name, fn, args, line, rate, pitch, zoom) in enumerate(plan):
        png = work / f"{n}_{name}.png"
        fn(png, *args)
        wav = work / f"{n}_{name}.wav"
        try:
            sec = tts_clip(line, wav, voice, rate, pitch)
        except Exception as e:
            print(f"[warn] voice failed ({name}): {e}")
            sec, wav = 0.0, None
        d = _grid(LEAD + sec + TAIL) if name.startswith("gallery") else max(MIN_SCENE, _grid(LEAD + sec + TAIL))
        if d > MAX_SCENE:
            print(f"[warn] scene {name} runs {d:.1f}s (> {MAX_SCENE}s): shorten its line: {line!r}")
        clips.append(wav if sec else None); durs.append(d); scenes.append(png); zooms.append(zoom); names.append(name); speech.append(sec)
    # 24 s cap: drop gallery shots from the end, then the features scene
    while sum(durs) > MAX_TOTAL and any(nm.startswith("gallery") or nm == "features" for nm in names):
        idx = max(i for i, nm in enumerate(names) if nm.startswith("gallery") or nm == "features")
        for lst in (clips, durs, scenes, zooms, names, speech):
            lst.pop(idx)
    audio = None
    if any(clips):
        audio = work / f"{n}.m4a"
        build_audio(clips, durs, audio)
    out = OUT / f"deal_{n}.mp4"
    render(scenes, durs, audio, out, zooms)
    # sync sheet for QA: every line must start after its scene begins and end before the next one
    off, sheet = 0.0, []
    for nm, d, sec in zip(names, durs, speech):
        sheet.append({"scene": nm, "start": round(off, 3), "end": round(off + d, 3),
                      "speech_start": round(off + LEAD, 3), "speech_end": round(off + LEAD + sec, 3)})
        assert off + LEAD + sec <= off + d + 1e-6, f"speech overruns scene {nm}"
        off += d
    (OUT / f"deal_{n}.sync.json").write_text(json.dumps({"total": round(off, 2), "scenes": sheet}, indent=1))
    vname = "ElevenLabs" if os.environ.get("ELEVENLABS_API_KEY") else (re.search(r"-([A-Za-z]+?)(?:Multilingual)?Neural$", voice) or [None, voice])[1]
    (OUT / f"deal_{n}.txt").write_text(caption(title, price, code, coupon, deal, _cat, was, pct) + "\n")
    (OUT / f"deal_{n}.meta.txt").write_text(f"Source deal: {deal['link']}\nVoice (A/B test): {vname}\nScenes: {', '.join(names)}  Total: {off:.1f}s\n")   # internal, never pasted
    return out


def main():
    deals = json.loads(DEALS_FILE.read_text()) if DEALS_FILE.exists() else []
    if AMAZON_PRICES != "hide":                       # shown price = Amazon's own morning check, stamped with that time
        from make_posts import fix_price
        for _d in deals:
            fix_price(_d)
    made = set(json.loads(MADE_FILE.read_text())) if MADE_FILE.exists() else set()
    picks = pick_deals(deals, made)
    OUT.mkdir(exist_ok=True)
    work = Path("build")
    work.mkdir(exist_ok=True)
    for n, deal in enumerate(picks, 1):
        print("made", make_one(n, deal, work), "-", deal["title"][:60])
        made.add(deal["id"])
    MADE_FILE.write_text(json.dumps(sorted(made)[-500:], indent=1))
    print(f"{len(picks)} videos made")


if __name__ == "__main__":
    main()
