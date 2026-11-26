"""Calendar of shopping moments (US). Bakes seasonal buying into the deals, posts and website.

active(today)            -> upcoming events whose lead-up window has started (soonest first)
matches(deals, event)    -> deals whose title/description fit the event's keywords
Each event: date, window (days before the date that people start shopping), theme headline,
words (match deal text), searches (extra Slickdeals keyword searches while the event is active).
Edit freely: add your own events or words.
"""
import re
from datetime import date

EVENTS = [
    dict(key="halloween", name="Halloween", date=date(2026, 10, 31), window=21, theme="Halloween finds",
         words=["halloween", "costume", "candy", "pumpkin", "trick or treat", "spooky"], searches=["halloween"]),
    dict(key="thanksgiving", name="Thanksgiving", date=date(2026, 11, 26), window=24, theme="Thanksgiving table",
         words=["thanksgiving", "turkey", "stuffing", "gravy", "cranberry", "pumpkin", "pie", "roasting pan", "baking",
                "casserole", "dinnerware", "tablecloth", "napkin", "serving", "carving", "dutch oven", "slow cooker",
                "instant pot", "air fryer", "mixer", "baking dish", "glass bakeware", "pantry", "broth", "butter", "flour",
                "mashed potato", "sweet potato", "fall decor", "harvest", "hostess", "host gift", "gift basket",
                "candle", "charcuterie", "cheese board", "wine glass", "throw blanket", "fire pit", "mug set"],
         searches=["thanksgiving", "turkey", "baking", "kitchen cookware"]),
    dict(key="football", name="Football season", date=date(2027, 2, 14), window=170, theme="Game day",
         words=["nfl", "football", "tailgate", "game day", "wings", "chips", "salsa", "dip", "grill", "jersey", "soundbar",
                "tv", "qled", "oled", "beer", "cooler", "snack", "popcorn", "pretzel", "super bowl", "projector"],
         searches=["football", "tailgate", "tv deals"]),
    dict(key="blackfriday", name="Black Friday", date=date(2026, 11, 27), window=14, theme="Black Friday early",
         words=["black friday", "doorbuster", "early access"], searches=["black friday amazon"]),
    dict(key="cybermonday", name="Cyber Monday", date=date(2026, 11, 30), window=10, theme="Cyber Monday",
         words=["cyber monday"], searches=["cyber monday amazon"]),
    dict(key="stocking", name="Stocking stuffers", date=date(2026, 12, 25), window=40, theme="Stocking stuffers",
         words=["stocking", "mini", "lip balm", "chapstick", "socks", "keychain", "playing cards", "fidget", "slime",
                "hot wheels", "funko", "candy cane", "chocolate", "candy", "ornament", "puzzle", "flashlight",
                "earbuds", "gloves", "beanie", "hand warmer", "scented candle", "bath bomb", "nail", "sticker",
                "magnetic tiles", "plush", "mario", "pop it", "squishy", "card game"],
         searches=["stocking stuffers", "stocking stuffer"]),
    dict(key="hanukkah", name="Hanukkah", date=date(2026, 12, 4), window=21, theme="Hanukkah gifts",
         words=["hanukkah", "menorah", "dreidel", "gelt"], searches=["hanukkah"]),
    dict(key="christmas", name="Christmas", date=date(2026, 12, 25), window=45, theme="Christmas gifts",
         words=["christmas", "xmas", "holiday", "tree", "lights", "ornament", "wrapping", "gift set", "advent",
                "lego", "board game", "gift", "santa", "elf", "wreath", "stockings"],
         searches=["christmas gifts", "christmas decor"]),
    dict(key="nye", name="New Year's Eve", date=date(2026, 12, 31), window=10, theme="New Year's Eve",
         words=["new year", "champagne", "party", "sparkler", "confetti", "balloon", "glitter"], searches=["new year party"]),
    dict(key="valentines", name="Valentine's Day / Super Bowl", date=date(2027, 2, 14), window=21, theme="Valentine's & Super Bowl",
         words=["valentine", "chocolate", "roses", "heart", "super bowl", "snack"], searches=["valentine"]),
    dict(key="easter", name="Easter", date=date(2027, 3, 28), window=21, theme="Easter basket",
         words=["easter", "basket", "egg", "bunny", "peeps"], searches=["easter"]),
    dict(key="mothers", name="Mother's Day", date=date(2027, 5, 9), window=21, theme="Mother's Day gifts",
         words=["mother", "mom", "spa", "jewelry", "candle", "robe", "perfume"], searches=["mothers day"]),
    dict(key="backtoschool", name="Back to school", date=date(2027, 8, 16), window=35, theme="Back to school",
         words=["backpack", "lunch box", "notebook", "pencil", "school supplies", "binder", "laptop"], searches=["back to school"]),
]


def active(today=None):
    today = today or date.today()
    out = []
    for e in EVENTS:
        days = (e["date"] - today).days
        lead = 3 if e["key"] in ("thanksgiving", "halloween") else 0     # shipping can't beat the day: stop food/decor themes 3 days out
        if lead <= days <= e["window"]:
            out.append(dict(e, days=days))
    return sorted(out, key=lambda e: e["days"])


def _hit(words, text):
    return [w for w in words if re.search(r"\b" + re.escape(w) + r"s?\b", text)]


def matches(deals, event):
    out = []
    for d in deals:
        text = f"{d.get('title', '')} {d.get('desc', '')}".lower()
        h = _hit(event["words"], text)
        if h:
            out.append((len(h), d))
    return [d for _, d in sorted(out, key=lambda x: -x[0])]


if __name__ == "__main__":
    import json
    deals = json.load(open("data/deals.json"))
    for e in active():
        m = [d for d in matches(deals, e) if d.get("asin")]
        print(f"{e['name']:28} in {e['days']:>3} days: {len(matches(deals, e)):>3} matches, {len(m)} with Amazon ID")
