"""Mom Found It Cheaper - faceless deal Reels.

Picks the best new deals from data/deals.json and makes a 1080x1920
vertical video for each: hook, product, price, code, call to action,
with an AI voiceover (free Microsoft Edge voices via edge-tts).
No product photos are used (Amazon rules), so it is text-and-motion.

Run:  python make_videos.py            (needs: pip install pillow edge-tts, and ffmpeg)
Out:  videos/deal_1.mp4 + deal_1.txt (caption to paste), ...
"""

import asyncio
import json
import random
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
BRAND = "Mom Found It Cheaper"
PINK, CREAM, INK, YELLOW = (255, 79, 139), (255, 247, 239), (34, 30, 40), (255, 214, 64)
VOICE = "en-US-JennyNeural"
VIDEOS_PER_RUN = 3
MAX_PRICE = 60.0
SKIP_WORDS = ("ebook", "ps5", "xbox", "steam", "pcdd", "gog", "resale", "kindle", "watch (")
DEALS_FILE = Path("data/deals.json")
MADE_FILE = Path("data/videos_made.json")
OUT = Path("videos")
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

HOOKS = [
    ("STOP SCROLLING,", "MAMA!"),
    ("DON'T PAY", "FULL PRICE!"),
    ("I FOUND IT", "CHEAPER!"),
    ("RUN, DON'T", "WALK!"),
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


# ---------- drawing scenes ----------

def font(size, bold=True):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


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


def centered(draw, y, text, fnt, fill, max_w=W - 140, gap=12):
    for line in wrap(draw, text, fnt, max_w):
        w = draw.textlength(line, font=fnt)
        draw.text(((W - w) / 2, y), line, font=fnt, fill=fill)
        y += fnt.size + gap
    return y


def brand_bar(draw, bg=INK, fg=CREAM):
    # Kept away from the top edge so the slow zoom never cuts it off.
    draw.rounded_rectangle([90, 130, W - 90, 250], radius=60, fill=bg)
    f = font(50)
    w = draw.textlength(BRAND.upper(), font=f)
    draw.text(((W - w) / 2, 160), BRAND.upper(), font=f, fill=fg)


def fit_font(draw, text, start, max_w):
    """Largest font size (from `start` down) that fits `text` on one line."""
    size = start
    while size > 40 and draw.textlength(text, font=font(size)) > max_w:
        size -= 6
    return font(size)


def scene_hook(path, hook):
    img = Image.new("RGB", (W, H), PINK)
    d = ImageDraw.Draw(img)
    brand_bar(d)
    y = 700
    for line in hook:
        y = centered(d, y, line, font(130), CREAM) + 20
    centered(d, y + 60, "Today's deal", font(60, False), INK)
    img.save(path)


def scene_product(path, title):
    img = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(img)
    brand_bar(d)
    d.rounded_rectangle([60, 500, W - 60, 1400], radius=50, fill="white", outline=PINK, width=10)
    centered(d, 560, "VIRAL FIND", font(56), PINK)
    centered(d, 700, title, font(84), INK, max_w=W - 220)
    img.save(path)


def scene_price(path, price, code, coupon):
    img = Image.new("RGB", (W, H), INK)
    d = ImageDraw.Draw(img)
    brand_bar(d, bg=PINK, fg=CREAM)
    centered(d, 520, "NOW JUST", font(80), CREAM)
    pf = fit_font(d, price, 280, W - 160)
    y = centered(d, 660, price, pf, YELLOW) + 80
    if code and code != "w/ code":
        d.rounded_rectangle([150, y, W - 150, y + 210], radius=30, fill=CREAM)
        centered(d, y + 25, "USE CODE", font(50, False), INK)
        centered(d, y + 95, code, font(90), PINK)
    elif coupon or code:
        d.rounded_rectangle([150, y, W - 150, y + 170], radius=30, fill=CREAM)
        centered(d, y + 45, "CLIP THE COUPON" if coupon else "PROMO CODE INSIDE", font(70), PINK)
    img.save(path)


def scene_cta(path):
    img = Image.new("RGB", (W, H), PINK)
    d = ImageDraw.Draw(img)
    brand_bar(d)
    y = centered(d, 600, "GRAB THE LINK", font(100), CREAM)
    y = centered(d, y, "IN OUR FREE", font(100), CREAM)
    y = centered(d, y + 10, "FACEBOOK GROUP", font(100), YELLOW)
    bf = fit_font(d, BRAND, 80, W - 320)
    d.rounded_rectangle([120, y + 80, W - 120, y + 120 + bf.size + 80], radius=40, fill=CREAM)
    centered(d, y + 120, BRAND, bf, PINK)
    centered(d, 1700, "#ad  -  prices and codes can change anytime", font(38, False), CREAM)
    img.save(path)


# ---------- voice and video ----------

async def make_voice(text, path):
    import edge_tts
    await edge_tts.Communicate(text, VOICE, rate="+8%").save(str(path))


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
        parts.append(f"[{last}][v{i}]xfade=transition=slideleft:duration={fade}:offset={offset:.2f}[x{i}]")
        last = f"x{i}"
    cmd += ["-filter_complex", ";".join(parts), "-map", f"[{last}]"]
    if audio:
        cmd += ["-map", f"{len(durations)}:a", "-c:a", "aac", "-b:a", "128k", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(out_path)]
    subprocess.run(cmd, check=True)


def caption(title, price, code, coupon):
    extra = f" Use code {code}." if code and code != "w/ code" else (" Clip the coupon!" if coupon else "")
    return (f"Mom found it cheaper! {title} - now just {price}.{extra}\n\n"
            f"Link in our free Facebook group: {BRAND}\n\n"
            "#ad #amazonfinds #momfinds #dealsforyou #founditcheaper #savemoney\n"
            "As an Amazon Associate I earn from qualifying purchases. Prices and codes can change.")


def make_one(n, deal, work):
    title = short_title(deal["title"])
    price, code, coupon = deal["price"], deal.get("code", ""), deal.get("coupon", "")
    hook = random.choice(HOOKS)
    s = [work / f"{n}_{i}.png" for i in range(4)]
    scene_hook(s[0], hook)
    scene_product(s[1], title)
    scene_price(s[2], price, code, coupon)
    scene_cta(s[3])

    said_code = f" Use code {' '.join(code)}." if code and code != "w/ code" else (" Just clip the coupon." if coupon else "")
    script = (f"{' '.join(hook).capitalize()} {title}. Now just {price}.{said_code} "
              f"Grab the link in our free Facebook group, {BRAND}.")
    audio = work / f"{n}.mp3"
    durations = [2.2, 3.8, 4.0, 3.5]
    try:
        asyncio.run(make_voice(script, audio))
        total = duration(audio) + 0.6
        scale = max(total / sum(durations), 1.0)
        durations = [d * scale for d in durations]
    except Exception as e:  # no voice? still make the video, silent
        print(f"[warn] voiceover failed: {e}")
        audio = None
    out = OUT / f"deal_{n}.mp4"
    render(s, durations, audio, out)
    (OUT / f"deal_{n}.txt").write_text(caption(title, price, code, coupon) + f"\n\nSource deal: {deal['link']}\n")
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
