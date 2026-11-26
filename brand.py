"""Brand tokens shared by build_site.py, make_posts.py, make_videos.py and the cover scripts.
One source of truth: change here, every surface follows. Evidence for each choice: brand/DESIGN.md.
Spec v2 (2026-11-25) after the consumer-psychology QA: light base, ONE hot accent for the number/button,
yellow stickers for state, green only for proof. No red or black backgrounds (owner rule).
"""

# ---- colors (RGB) ----
CREAM = (255, 246, 236)       # page base
WHITE = (255, 255, 255)       # card
INK = (31, 26, 46)            # text; 15.8:1 on cream. Never pure black.
MUTED = (96, 88, 110)         # secondary text; 6.3:1 on cream
TANGERINE = (194, 65, 12)     # THE accent: tier number, primary button. White on it 5.2:1. <=10% of any screen.
YELLOW = (255, 197, 61)       # sticker fill, INK text (10.7:1). The "stop" color. <=5% of any screen.
GREEN = (15, 118, 110)        # proof only ("Checked 7:12 AM"). White on it 5.5:1. Never a CTA.
MINT = (215, 243, 230)        # section band / blob
LAVENDER = (237, 231, 255)    # section band / blob
PEACH = (255, 232, 176)       # section band / blob
WAS_RED = (185, 28, 28)       # strikethrough color only, only on real >=30% drops. Never a fill.

HEX = {k: "#%02X%02X%02X" % v for k, v in dict(
    CREAM=CREAM, WHITE=WHITE, INK=INK, MUTED=MUTED, TANGERINE=TANGERINE, YELLOW=YELLOW, GREEN=GREEN,
    MINT=MINT, LAVENDER=LAVENDER, PEACH=PEACH, WAS_RED=WAS_RED).items()}

# ---- type ----
FONT_TEXT = "fonts/Inter.ttf"                 # everything: display, numbers, body
FONT_WORDMARK = "fonts/PlayfairDisplay.ttf"   # the wordmark "Mom Found It Cheaper" only
FONT_HAND = "fonts/Caveat-Bold.ttf"           # one handwritten word on a sticker, at most
SCALE = dict(display=64, number=52, h2=32, title=18, meta=13, chip=12)   # px, desktop

# ---- composition rules ----
MAX_HEADLINE_WORDS = 5
STICKER_ANGLE = -6
STICKERS = ("BF DEAL", "UNDER $10", "UNDER $20", "UNDER $25", "UNDER $50", "PRICE DROPPED", "BACK IN STOCK", "MIA'S PICK")
CARD_ORDER = ("photo+sticker", "tier number", "title", "proof row", "button")
MIA_AVATAR = "brand/mia_avatar_circle_240.png"
MIA_SCENE = "brand/mia_hero_scene.png"


def tier(price):
    """Big-number stand-in for the price. Returns 'Under $25' style text or ''."""
    if price is None:
        return ""
    for cap in (10, 15, 20, 25, 30, 50, 75, 100, 150, 200, 300, 500, 1000, 1500, 2000):
        if price < cap:
            return f"Under ${cap}"
    return ""
