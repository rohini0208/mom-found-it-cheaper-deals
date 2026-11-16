"""Facebook group cover (1640x856). Run: python launch/make_cover.py"""
import sys
sys.path.insert(0, ".")
from PIL import Image, ImageDraw
from make_videos import sans

W, H = 1640, 856
img = Image.new("RGB", (W, H), (255, 143, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle([60, 60, W - 60, H - 60], 48, fill=(255, 255, 255))


def c(y, text, font, fill):
    d.text(((W - d.textlength(text, font=font)) / 2, y), text, font=font, fill=fill)


c(120, "MOM FOUND IT CHEAPER", sans(104, "Bold"), (33, 33, 33))
c(262, "Real Amazon deals, checked daily", sans(58, "SemiBold"), (230, 81, 0))
pills = [("REAL PHOTOS", (46, 160, 90)), ("PRICE + WAS PRICE", (0, 137, 123)), ("STAR RATINGS", (21, 101, 192))]
f = sans(40, "Bold")
ws = [d.textlength(t, font=f) + 70 for t, _ in pills]
x = (W - (sum(ws) + 40 * (len(ws) - 1))) / 2
for (txt, col), w in zip(pills, ws):
    d.rounded_rectangle([x, 410, x + w, 500], 45, fill=col)
    d.text((x + 35, 430), txt, font=f, fill=(255, 255, 255))
    x += w + 40
c(570, "Free group  \u00b7  New finds every day  \u00b7  Share yours too", sans(44, "Medium"), (90, 90, 90))
c(690, "Some links are affiliate links. We earn from qualifying Amazon purchases.", sans(28, "Medium"), (140, 140, 140))
img.save("launch/group_cover.png")
print("saved launch/group_cover.png")
