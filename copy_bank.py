"""Wording bank for Reels and posts. Many variants so no two days sound the same.

Pick is stable per deal (hash of its id) and avoids the same variant twice in a row.
Edit freely: add your own lines in your own voice. Keep each line honest (no fake
urgency, no "lowest ever" unless the data says so).
"""

import hashlib

HOOKS = {
    "default": [("Stop scrolling,", "mama."), ("Don't pay", "full price."), ("I found it", "cheaper."),
                ("Your new", "favorite find."), ("Quick, before", "it moves."), ("Mom-approved", "price drop."),
                ("This one", "caught my eye."), ("Small price,", "big win.")],
    "Baby & Kids": [("Parents,", "look at this."), ("Kid stuff,", "cheaper today."), ("Tired mama?", "Save here.")],
    "Toys & Games": [("Gift idea", "for less."), ("Playtime,", "cheaper today."), ("Holiday list?", "Check this.")],
    "Beauty & Health": [("Self-care,", "cheaper."), ("Glow for", "less."), ("Treat yourself,", "not your wallet.")],
    "Home & Kitchen": [("Kitchen find,", "cheaper today."), ("Home upgrade,", "small price."), ("Your kitchen", "needs this.")],
    "Fashion": [("Style for", "less."), ("Closet find,", "cheaper today."), ("Wear it,", "don't overpay.")],
    "Tech & Electronics": [("Tech price", "drop."), ("Gadget alert,", "cheaper."), ("Upgrade for", "less.")],
    "Pets": [("Pet parents,", "look."), ("Spoil them,", "spend less."), ("Fur-baby find,", "cheaper today.")],
    "Grocery & Household": [("Pantry find,", "cheaper today."), ("Household", "savings."), ("Restock for", "less.")],
    "Gaming & Entertainment": [("Game on,", "pay less."), ("Fun find,", "cheaper today.")],
    "Sports & Fitness": [("Move more,", "spend less."), ("Fitness find,", "cheaper today.")],
    "Holiday & Seasonal": [("Holiday find,", "cheaper today."), ("Deck the halls", "for less.")],
    "Office & School": [("Desk upgrade,", "small price."), ("Back-to-it", "savings.")],
    "Outdoor & Tools": [("Tool deal,", "cheaper today."), ("Fix-it find", "for less."), ("Outdoor gear,", "price drop.")],
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
