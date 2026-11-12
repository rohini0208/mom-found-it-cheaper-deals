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
import json
import os
import random
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
BRAND = "Mom Found It Cheaper"
VOICE = os.environ.get("VOICE") or "en-US-AvaMultilingualNeural"   # warm, expressive; pick yours from the voice samples
VOICE_RATE = os.environ.get("VOICE_RATE", "+6%")
VOICE_PITCH = os.environ.get("VOICE_PITCH", "+2Hz")
VIDEOS_PER_RUN = int(os.environ.get("VIDEOS_PER_RUN") or "8")   # Reels per day
MAX_PRICE = 60.0
SKIP_WORDS = ("ebook", "ps5", "xbox", "steam", "pcdd", "gog", "resale", "kindle", "watch (")
DEALS_FILE = Path("data/deals.json")
MADE_FILE = Path("data/videos_made.json")
OUT = Path("videos")
SITE = os.environ.get("SITE_URL", "https://mom-found-it-cheaper-deals.pages.dev/")

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
    t = re.sub(r"^(select accts?|select accounts|prime|amazon)\s*[:\-–]\s*", "", title, flags=re.I)
    t = re.split(r"\s+(?:for\s+)?(?:from\s+)?\$\d", t)[0]      # cut "... for $12 + free shipping"
    t = re.sub(r"^\$[\d.,]+\*?\s*/\s*", "", t)                   # "$28* / LEGO ..." -> "LEGO ..."
    return t.strip(" -–,|")[:90]


def pick_deals(deals, made):
    good = []
    for d in deals:
        price = price_value(d.get("price", ""))
        low = d["title"].lower()
        if d["id"] in made or price is None or price > MAX_PRICE or price < 1:
            continue
        if any(w in low for w in SKIP_WORDS):
            continue
        score = (2 if d.get("code") and d["code"] != "w/ code" else 0) + (1 if d.get("coupon") else 0)
        good.append((score, d["seen"], d))
    good.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [d for _, _, d in good[:VIDEOS_PER_RUN]]


# ---------- drawing scenes (elegant editorial look) ----------
# Ivory paper, deep charcoal, champagne gold. Playfair Display headlines,
# Inter for small caps labels. Thin gold rules instead of boxes.

IVORY, CHAR, GOLD, MUTED, BLUSH = (246, 240, 231), (22, 21, 24), (201, 164, 106), (120, 112, 104), (232, 190, 186)
FONTS = Path(__file__).parent / "fonts"


WEIGHTS = {"Regular": 400, "Medium": 500, "SemiBold": 600, "Bold": 700}


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


def masthead(draw, color, y=170):
    centered(draw, y, BRAND.upper(), sans(34, "SemiBold"), color, spacing=9)
    rule(draw, y + 70, 120, GOLD)


def footer(draw, color):
    centered(draw, 1760, "#AD  ·  PRICES CAN CHANGE", sans(28, "Medium"), color, spacing=5)


def badge_text(deal):
    """Only real signals from the deal itself - never invented."""
    if deal.get("new"):
        return "NEW RELEASE"
    if deal.get("bestseller"):
        return "BEST SELLER"
    t = deal.get("thumbs", 0)
    if t >= 30:
        return f"COMMUNITY FAVORITE  ·  +{t} VOTES"
    if t >= 10:
        return f"TRENDING  ·  +{t} VOTES"
    return "TODAY'S FIND"


def scene_hook(path, hook):
    img = Image.new("RGB", (W, H), IVORY)
    d = ImageDraw.Draw(img)
    masthead(d, CHAR)
    centered(d, 640, hook[0], serif(120, "Regular", italic=True), CHAR)
    centered(d, 800, hook[1], serif(150, "Bold"), CHAR)
    rule(d, 1040, 160)
    centered(d, 1090, "TODAY'S FIND", sans(36, "SemiBold"), MUTED, spacing=8)
    img.save(path)


def scene_product(path, title, deal):
    img = Image.new("RGB", (W, H), CHAR)
    d = ImageDraw.Draw(img)
    masthead(d, IVORY)
    badge = badge_text(deal)
    bf = sans(32, "SemiBold")
    bw = sum(d.textlength(c, font=bf) for c in badge) + 6 * (len(badge) - 1) + 80
    d.rounded_rectangle([(W - bw) / 2, 640, (W + bw) / 2, 720], radius=40, outline=GOLD, width=3)
    centered(d, 660, badge, bf, GOLD, spacing=6)
    tf = fit(d, title, lambda s: serif(s, "SemiBold"), 112, W - 200, max_lines=4)
    y = centered(d, 840, title, tf, IVORY, gap=18)
    rule(d, y + 50, 160)
    img.save(path)


def scene_features(path, features):
    img = Image.new("RGB", (W, H), IVORY)
    d = ImageDraw.Draw(img)
    masthead(d, CHAR)
    centered(d, 520, "Why moms love it", serif(96, "Regular", italic=True), CHAR)
    rule(d, 670, 160)
    y = 800
    for i, feat in enumerate(features[:3], 1):
        centered(d, y, f"0{i}", serif(64, "Bold"), GOLD)
        y = centered(d, y + 90, feat, sans(54, "Medium"), CHAR, max_w=W - 240, gap=10) + 70
    img.save(path)


def scene_price(path, price, was, code, coupon):
    img = Image.new("RGB", (W, H), CHAR)
    d = ImageDraw.Draw(img)
    masthead(d, IVORY)
    y = 640
    if was:
        wf = serif(80, "Regular")
        label = f"was {was}"
        w = d.textlength(label, font=wf)
        d.text(((W - w) / 2, y), label, font=wf, fill=MUTED)
        d.line([((W - w) / 2 - 10, y + 58), ((W + w) / 2 + 10, y + 58)], fill=BLUSH, width=5)
        y += 140
    else:
        y = centered(d, y, "NOW ONLY", sans(40, "SemiBold"), MUTED, spacing=8) + 30
    pf = fit(d, price, lambda s: serif(s, "Bold"), 300, W - 200, max_lines=1, min_size=120)
    y = centered(d, y, price, pf, GOLD) + 130
    if code and code != "w/ code":
        centered(d, y, "WITH CODE", sans(34, "SemiBold"), MUTED, spacing=8)
        cf = sans(80, "Bold")
        cw = sum(d.textlength(c, font=cf) for c in code) + 10 * (len(code) - 1)
        d.rounded_rectangle([(W - cw) / 2 - 60, y + 70, (W + cw) / 2 + 60, y + 210], radius=16, outline=GOLD, width=3)
        centered(d, y + 95, code, cf, IVORY, spacing=10)
    elif coupon or code:
        centered(d, y, "CLIP THE COUPON" if coupon else "PROMO CODE INSIDE", sans(48, "SemiBold"), IVORY, spacing=8)
    footer(d, MUTED)
    img.save(path)


def scene_cta(path):
    img = Image.new("RGB", (W, H), IVORY)
    d = ImageDraw.Draw(img)
    centered(d, 560, "The link is waiting in our", serif(76, "Regular", italic=True), CHAR)
    centered(d, 680, "free Facebook group", serif(76, "Regular", italic=True), CHAR)
    rule(d, 850, 160)
    centered(d, 920, "Mom Found", serif(150, "Bold"), CHAR)
    centered(d, 1090, "It Cheaper", serif(150, "Bold"), GOLD)
    rule(d, 1310, 160)
    centered(d, 1360, "JOIN FREE  ·  NEW DEALS DAILY", sans(34, "SemiBold"), MUTED, spacing=7)
    footer(d, MUTED)
    img.save(path)


# ---------- voice and video ----------

async def make_voice(text, path, voice=None):
    """Premium ElevenLabs voice if ELEVENLABS_API_KEY is set (free tier ~10k characters/month),
    otherwise a free Microsoft Edge neural voice."""
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
            Path(path).write_bytes(r.read())
        return
    import edge_tts
    await edge_tts.Communicate(text, voice or VOICE, rate=VOICE_RATE, pitch=VOICE_PITCH).save(str(path))


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return float(out.stdout.strip() or 0)


def render(scenes, durations, audio, out_path):
    """Slow zoom on each scene, crossfade between them, voice on top."""
    fade = 0.4
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    # One still image per input: zoompan turns that single frame into
    # `frames` frames. (Looping the image here would multiply the length.)
    for s in scenes:
        cmd += ["-i", str(s)]
    if audio:
        cmd += ["-i", str(audio)]
    parts, fps = [], 30
    for i, dur in enumerate(durations):
        frames = int((dur + fade) * fps)
        parts.append(
            f"[{i}:v]scale=1134:2016,zoompan=z='min(1+0.0004*on,1.04)':d={frames}"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={fps},setsar=1[v{i}]"
        )
    last, offset = "v0", 0.0
    for i in range(1, len(durations)):
        offset += durations[i - 1]
        parts.append(f"[{last}][v{i}]xfade=transition=fade:duration={fade}:offset={offset:.2f}[x{i}]")
        last = f"x{i}"
    cmd += ["-filter_complex", ";".join(parts), "-map", f"[{last}]"]
    if audio:
        cmd += ["-map", f"{len(durations)}:a", "-c:a", "aac", "-b:a", "128k", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(out_path)]
    subprocess.run(cmd, check=True)


def caption(title, price, code, coupon, deal=None):
    extra = f" Use code {code}." if code and code != "w/ code" else (" Clip the coupon!" if coupon else "")
    return (f"Mom found it cheaper! {title} - now just {price}.{extra}\n\n"
            f"Get it here: {SITE}#d-{hashlib.sha1(deal['id'].encode()).hexdigest()[:10] if deal else ''}\n"
            f"More deals daily in our free Facebook group: {BRAND}\n\n"
            "#ad #amazonfinds #momfinds #dealsforyou #founditcheaper #savemoney\n"
            "As an Amazon Associate I earn from qualifying purchases. Prices and codes can change.")


def make_one(n, deal, work):
    title = short_title(deal["title"])
    price, code, coupon = deal["price"], deal.get("code", ""), deal.get("coupon", "")
    was, feats = deal.get("was", ""), deal.get("features", [])
    hook = random.choice(HOOKS)
    scenes, durations = [], []

    def add(name, dur, fn, *args):
        path = work / f"{n}_{name}.png"
        fn(path, *args)
        scenes.append(path)
        durations.append(dur)

    add("hook", 2.2, scene_hook, hook)
    add("product", 3.6, scene_product, title, deal)
    if feats:
        add("features", 4.2, scene_features, feats)
    add("price", 3.8, scene_price, price, was, code, coupon)
    add("cta", 3.4, scene_cta)

    said_code = f" Use code {' '.join(code)}." if code and code != "w/ code" else (" Just clip the coupon." if coupon else "")
    said_was = f" It's usually {was}." if was else ""
    said_feats = (" " + ". ".join(feats[:2]) + ".") if feats else ""
    opener = random.choice(["Okay, you need to see this!", "Oh, this one's good.", "Mama, stop scrolling for a sec!",
                            "I just found something you're going to love."])
    script = (f"{opener} {title}.{said_feats}{said_was} And right now? It's only {price}!{said_code} "
              f"Hurry, deals like this go fast. The link is waiting for you at {BRAND}.")
    audio = work / f"{n}.mp3"
    try:
        asyncio.run(make_voice(script, audio))
        total = duration(audio) + 0.6
        scale = max(total / sum(durations), 1.0)
        durations = [d * scale for d in durations]
    except Exception as e:  # no voice? still make the video, silent
        print(f"[warn] voiceover failed: {e}")
        audio = None
    out = OUT / f"deal_{n}.mp4"
    render(scenes, durations, audio, out)
    (OUT / f"deal_{n}.txt").write_text(caption(title, price, code, coupon, deal) + f"\n\nSource deal: {deal['link']}\n")
    return out


def main():
    deals = json.loads(DEALS_FILE.read_text()) if DEALS_FILE.exists() else []
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
