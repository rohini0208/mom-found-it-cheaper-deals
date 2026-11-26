"""Brand tokens shared by build_site.py, make_posts.py, make_videos.py and the cover scripts.
Every visual we ship reads from here, so one change restyles everything. See brand/DESIGN.md
for the research each choice rests on.
"""

# Colors (RGB). Soft base, one loud accent. Women prefer softer blues/greens; the accent must be the
# only saturated thing on the card so the eye lands on the price/CTA (isolation effect).
PEACH = (255, 214, 186)      # base light
MINT = (190, 232, 214)       # base light 2
CREAM = (255, 248, 238)      # card background
CHAR = (43, 33, 24)          # text, 12:1 on cream
MUTED = (110, 96, 84)        # secondary text, 5.6:1 on cream
CORAL = (232, 93, 74)        # the ONE accent: price, CTA, hook word. White text on coral = 3.9:1 (large text only)
CORAL_DARK = (184, 67, 0)    # accent for small text/buttons on light (4.9:1 with white)
GOLD = (240, 180, 70)        # sparkle/badge only, never text
LAVENDER = (214, 200, 240)   # third pastel for variety

HEX = {k: "#%02X%02X%02X" % v for k, v in dict(PEACH=PEACH, MINT=MINT, CREAM=CREAM, CHAR=CHAR, MUTED=MUTED,
                                               CORAL=CORAL, CORAL_DARK=CORAL_DARK, GOLD=GOLD, LAVENDER=LAVENDER).items()}

# Type. Display serif for warmth/trust, humanist sans for reading, handwritten only for one sticker word.
FONT_DISPLAY = "fonts/PlayfairDisplay.ttf"
FONT_DISPLAY_ITALIC = "fonts/PlayfairDisplay-Italic.ttf"
FONT_TEXT = "fonts/Inter.ttf"
FONT_HAND = "fonts/Caveat-Bold.ttf"

# Composition rules (enforced by callers)
MAX_HEADLINE_WORDS = 5       # breakout thumbnails cluster at 4-6 overlay words
PRICE_IS_THE_HOOK = True     # biggest element after the photo is the price (or "See price" when hidden)
ONE_FACE = True              # Mia appears once, eye contact, genuine smile, never exaggerated
STICKER_ANGLE = -3           # drawn-on elements (stickers, circles, arrows) give a small measurable edge
MIA_AVATAR = "brand/mia_avatar_circle_240.png"
MIA_SCENE = "brand/mia_cover_scene.png"
