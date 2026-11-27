"""Wording bank for Reels and posts. Many variants so no two days sound the same.

Pick is stable per deal (hash of its id) and avoids the same variant twice in a row.
Edit freely: add your own lines in your own voice. Keep each line honest (no fake
urgency, no "lowest ever" unless the data says so).
"""

import hashlib

# Hooks are benefit / curiosity lines (trend benchmark 2026-11-26: winners never open on a price or "deal alert").
HOOKS = {
    "default": [("This one's", "actually worth it."), ("The find", "moms keep sharing."), ("Okay, this is", "a good one."),
                ("Small thing,", "big difference."), ("You'll use this", "every single day."), ("Saw it,", "had to share.")],
    "Baby & Kids": [("Makes mornings", "so much easier."), ("Little kids", "love this one."), ("The mom hack", "nobody told you.")],
    "Toys & Games": [("Keeps them busy", "for hours."), ("Gift closet,", "sorted."), ("The toy they'll", "actually play with.")],
    "Beauty & Health": [("Five minutes,", "feels like a spa."), ("The one everyone", "keeps asking about."), ("Self-care that", "fits a mom's day.")],
    "Home & Kitchen": [("Dinner, done", "in half the time."), ("Clutter gone,", "counter back."), ("The kitchen upgrade", "you'll use daily.")],
    "Fashion": [("Love this look.", "Wait for the price."), ("Comfy enough", "for school pickup."), ("The piece that", "goes with everything.")],
    "Tech & Electronics": [("Peace of mind,", "one little gadget."), ("Set it once,", "forget it."), ("The upgrade", "you'll notice daily.")],
    "Pets": [("Your dog's", "new favorite thing."), ("Happy pet,", "tidy house."), ("Pet parents,", "look at this.")],
    "Grocery & Household": [("Restock day,", "made easy."), ("The pantry staple", "everyone's grabbing."), ("Chores,", "faster.")],
    "Gaming & Entertainment": [("Family game night,", "sorted."), ("Screen-free fun", "they'll beg for.")],
    "Sports & Fitness": [("Workout at home,", "no excuses."), ("Move more,", "the easy way.")],
    "Holiday & Seasonal": [("Holiday magic,", "zero stress."), ("Deck the halls", "the easy way.")],
    "Office & School": [("Homework spot,", "sorted."), ("Desk upgrade", "you'll feel.")],
    "Outdoor & Tools": [("Fix it yourself,", "this weekend."), ("Backyard ready", "in one afternoon.")],
}

OPENERS = [
    "Okay, you need to see this!", "Oh, this one's good.", "Mama, stop scrolling for a sec!",
    "I just found something you might love.", "Look what showed up cheaper today.",
    "Heads up, this just dropped.", "This one made me look twice.", "Quick find for you.",
    "Ok, this is a good one.", "Found one worth sharing.",
]

CLOSERS = [
    "The link is in the caption. Check the price before you buy, it can change. More finds every day at {brand}.",
    "Link's in the caption. Prices move, so look before you buy. New finds daily at {brand}.",
    "You'll find the link in the caption. Double check the price first. More at {brand}.",
    "Tap the link in the caption to see today's price. We post more finds every day at {brand}.",
]

FEATURES_TITLES = ["Why it's a good find", "What you get", "Worth a look", "Why we like it"]

PERSONAL = [
    "Saved this one for you.", "This is the kind of find I'd send my sister.",
    "Checked it twice before sharing.", "One for the cart, maybe.", "Small win for today.",
]


def _h(key, salt=""):
    return int(hashlib.sha1((salt + key).encode()).hexdigest(), 16)


def pick(options, key, salt="", avoid=None):
    """Stable choice from options; if it equals `avoid` (previous pick), take the next one."""
    i = _h(key, salt) % len(options)
    if avoid is not None and len(options) > 1 and options[i] == avoid:
        i = (i + 1) % len(options)
    return options[i]


def hook_for(category, key, avoid=None):
    pool = HOOKS["default"] + HOOKS.get(category, [])
    return pick(pool, key, "hook", avoid)
