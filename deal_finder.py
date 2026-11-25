"""Mom Found It Cheaper - daily deal finder (Amazon, Walmart, Target and more).

Pulls public RSS feeds from Slickdeals and DealNews, tags each deal by store
and category, and writes one list: DEALS.md (readable in the GitHub app) and
deals.html. No Claude, no API keys, standard library only.

Run:  python deal_finder.py
"""

import html
import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

FEEDS = {
    "Slickdeals Frontpage": "https://slickdeals.net/newsearch.php?mode=frontpage&searcharea=deals&searchin=first&rss=1",
    "Slickdeals Popular": "https://slickdeals.net/newsearch.php?mode=popdeals&searcharea=deals&searchin=first&rss=1",
    "Slickdeals Coupons": "https://slickdeals.net/newsearch.php?searchin=first&forumchoice%5B%5D=10&rss=1",
    "DealNews Home & Garden": "https://www.dealnews.com/c196/Home-Garden/?rss=1",
    "DealNews Clothing": "https://www.dealnews.com/c202/Clothing-Accessories/?rss=1",
    "DealNews Health & Beauty": "https://www.dealnews.com/c756/Health-Beauty/?rss=1",
    "DealNews Toys": "https://www.dealnews.com/c186/Gaming-Toys/?rss=1",
    "DealNews Electronics": "https://www.dealnews.com/c142/Electronics/?rss=1",
    "DealNews Sports & Fitness": "https://www.dealnews.com/c211/Sports-Fitness/?rss=1",
    "DealNews Computers": "https://www.dealnews.com/c39/Computers/?rss=1",
    "Slickdeals Hot Deals": "https://slickdeals.net/newsearch.php?searchin=first&forumchoice%5B%5D=9&rss=1",
}
# camelcamelcamel: public RSS of the biggest Amazon price drops across ALL products.
# Hip2Save: mom-focused, Amazon-heavy, every post has a product image (only items in its "Amazon" category are kept).
for _p in (1, 2, 3):
    FEEDS[f"Hip2Save p{_p}"] = "https://hip2save.com/feed/" + (f"?paged={_p}" if _p > 1 else "")
FEEDS["Amazon price drops (daily)"] = "https://camelcamelcamel.com/top_drops/feed?t=daily"
FEEDS["Amazon price drops (weekly)"] = "https://camelcamelcamel.com/top_drops/feed?t=weekly"
# Seasonal searches: while an event (Thanksgiving, stocking stuffers, football...) is in its lead-up window
# we also search the deal feeds for it. See seasonal.py.
try:
    from seasonal import active as _active
    for _e in _active():
        for _kw in _e["searches"]:
            FEEDS[f"Slickdeals season: {_kw}"] = ("https://slickdeals.net/newsearch.php?q=" + urllib.parse.quote_plus(_kw)
                                                  + "&searcharea=deals&searchin=first&rss=1")
except Exception as _e:
    print("[warn] seasonal feeds:", _e)
# Long-tail Amazon finds (cheap beauty, kids, jewelry...) that the front-page feeds miss.
# Slickdeals keyword searches, same RSS format as the feeds above.
for _kw in ("amazon beauty", "amazon skincare", "amazon baby", "amazon kitchen", "amazon pet",
            "amazon tools", "amazon toys", "amazon jewelry", "amazon home", "amazon clothing"):
    FEEDS["Slickdeals search: " + _kw.split()[1]] = (
        "https://slickdeals.net/newsearch.php?q=" + urllib.parse.quote_plus(_kw)
        + "&searcharea=deals&searchin=first&rss=1")

STORES = ["Amazon", "Walmart", "Target", "Best Buy", "Costco", "Home Depot", "Lowe's", "Kohl's",
          "Macy's", "eBay", "Woot", "Sam's Club", "Old Navy", "Nike", "Adidas", "Wayfair", "Ulta",
          "Sephora", "Dell", "Lenovo", "Newegg", "Staples", "Kroger", "Dollar General", "CVS", "Walgreens"]

CATEGORIES = {
    # phrases are matched on word boundaries; longer/more specific phrases score higher (see category_of)
    "Baby & Kids": ["baby bottle", "bottle sterilizer", "bottle warmer", "play-doh", "kids' toys", "baby", "toddler", "infant", "diaper", "wipes", "stroller", "car seat", "nursery", "kids'", "kids", "children", "pacifier", "crib", "playpen"],
    "Toys & Games": ["fisher-price", "little tikes", "little people", "g.i. joe", "my little pony", "wiggle car", "action figures", "inflatable tube", "tube man", "activity walker", "ride on", "karaoke", "trading card", "trading cards", "tcg", "booster", "booster box", "pokemon", "pokémon", "magic: the gathering", "diecast", "collectibles", "connect 4", "retro game console", "game console", "hot air balloon-never", "rc car", "remote control car", "monster truck", "ride-on", "play-doh", "dollhouse", "doll house", "modeling compound", "craft kit", "diy kit", "toy", "toys", "lego", "puzzle", "plush", "playset", "doll", "nerf", "board game", "building block", "building blocks", "action figure", "roleplay", "marvel legends", "star wars", "funko", "hot wheels", "barbie", "paw patrol", "squishmallow", "playmobil", "card game"],
    "Holiday & Seasonal": ["christmas", "xmas", "santa", "ornament", "ornaments", "wrapping paper", "advent", "halloween", "stocking", "stockings", "reindeer", "snowman", "holiday", "thanksgiving", "pumpkin", "wreath", "garland", "gift wrap", "gift bag", "gift bags", "countdown"],
    "Office & School": ["pen", "pens", "pencil", "refill", "ink", "cartridge", "printing", "labels", "notebook", "planner", "stapler", "binder", "backpack school", "school supplies", "desk organizer", "calculator", "sticky notes", "markers", "highlighter", "paper"],
    "Gaming & Entertainment": ["(switch)", "switch)", "@ fanatical", "complete series", "4k ultra hd", "guitar", "electric guitar", "fanatical", "nintendo", "switch 2", "playstation", "ps5", "ps4", "xbox", "steam", "pc digital download", "video game", "meta quest", "vr headset", "gaming", "gamer", "blu-ray", "4k uhd", "dvd", "vinyl", "cd", "movie", "tickets", "subscription", "streaming", "lifetime subscription"],
    "Beauty & Health": ["moisturizing cream", "aloe", "body mist", "mini mist", "fragrance", "hand soap", "protein powder", "shower steamers", "cream", "gel", "gift set", "mouthwash", "toothbrushes", "grooming", "personal care", "heating pad", "sonicare", "scalp massager", "pilates kit-never", "charlotte tilbury", "colgate", "pore", "face towels", "face towel", "mask sheets", "aircurlers", "curling", "curler", "hair dryer", "straightener", "cashmere-never", "nail polish", "tooth", "oral", "dental", "water flosser", "cologne", "eau de toilette", "parfum", "beauty", "skin", "skincare", "serum", "moisturizer", "hair", "makeup", "mascara", "lipstick", "perfume", "eau de parfum", "cologne", "fragrance", "vitamin", "supplement", "massager", "toothbrush", "shaver", "razor", "trimmer", "body care", "body wash", "lotion", "shampoo", "conditioner", "red light therapy", "face mask", "sunscreen", "nail", "health", "blood pressure", "thermometer", "first aid"],
    "Pets": ["for pets", "pet bed", "pet hair", "bug zapper-never", "dog", "dogs", "cat", "cats", "pet", "pets", "litter", "puppy", "kitten", "aquarium", "leash"],
    "Tech & Electronics": ["smart lock", "door lock", "walkie talkie", "walkie talkies", "security system", "security cameras", "aio", "liquid cooler", "cpu cooler", "microphone", "wireless microphone", "digital calendar", "smartphone", "phones", "mount", "tripod", "gimbal", "joby", "motherboard", "tp-link", "networking", "media converter", "bose", "polk audio", "klipsch", "chromebook", "apple", "sonos", "anker", "software", "turbotax", "tax software", "bass module", "samsung galaxy", "verizon", "smart scale", "lenovo", "gigabyte", "logitech", "nvidia", "amd", "intel", "ram", "raid", "nas", "wireless charging", "charging pad", "qi2", "magsafe", "dji", "osmo", "garmin", "gimbal", "samsung galaxy", "samsung", "translation glasses", "ai voice recorder", "voice recorder", "ai agent", "smart ring", "ring s1", "wi-fi music", "hi-res audio", "gopro", "action camera", "led strip", "strip light", "smart lamp", "charger", "usb", "usb-c", "headphones", "earbuds", "laptop", "monitor", "tv", "tvs", "4k tv", "ssd", "hard drive", "flash drive", "sd card", "microsd", "phone", "iphone", "android", "power bank", "camera", "webcam", "speaker", "tablet", "ipad", "jbl", "bluetooth", "soundbar", "fire tv", "roku", "qled", "oled", "router", "wi-fi", "wifi", "smart watch", "smartwatch", "apple watch", "airpods", "kindle", "echo", "alexa", "smart home", "smart plug", "smart bulb", "security camera", "solocam", "doorbell", "3d printer", "printer", "keyboard", "mouse", "gpu", "cable", "adapter", "streamer", "stereo", "projector", "drone", "dash cam", "jump starter", "power station", "led tv backlight", "tv backlight", "tech"],
    "Fashion": ["skirt", "skirts", "joggers", "crossbody", "shoulder bags", "shoulder bag", "reflective vest", "dooney", "victoria's secret", "athletic shoe", "new balance", "shoe", "slipper", "clog", "duffel", "luggage", "suitcase", "travel bag", "tote", "clog", "clogs", "crocs", "cashmere", "outerwear", "denim", "suit", "suits", "polo", "ralph lauren", "carhartt", "lululemon", "j.crew", "cole haan", "apparel", "women's", "men's", "mens", "womens", "shirt", "tee", "tees", "dress", "jeans", "shoes", "sneakers", "jacket", "coat", "socks", "bag", "handbag", "purse", "pants", "shorts", "sweater", "hoodie", "boots", "beanie", "hat", "gloves", "scarf", "sunglasses", "aviator", "watch", "jewelry", "necklace", "earrings", "leggings", "pajamas", "slippers", "underwear", "bra", "wallet", "belt", "apparel", "nike", "adidas", "reebok", "levi's", "puma", "under armour", "ray-ban"],
    "Sports & Fitness": ["pool table", "air hockey", "foosball", "schwinn", "franklin sports", "sports card", "sports cards", "athletic shoe", "pilates", "pickleball paddle", "sports", "sports tracking", "sports fan", "fan shop", "mls", "nfl", "nba", "nhl", "mlb", "golf+", "fitness", "gym", "home gym", "workout", "dumbbell", "kettlebell", "weights", "weight bench", "squat rack", "monster rack", "treadmill", "yoga", "peloton", "exercise", "resistance band", "baseball", "mitt", "golf", "football", "basketball", "soccer", "tennis", "pickleball", "fishing", "rod", "spinning combo", "reel", "bike", "bicycle", "scooter", "skateboard", "snowboard", "ski", "kayak", "paddle", "sporting goods", "memorabilia", "autographed", "jersey"],
    "Outdoor & Tools": ["pocketknife", "pocket knife", "folding knife", "benchmade", "leatherman", "kreg", "jig", "drilling set", "tape measure", "laser", "griddle", "blackstone", "turkey fryer", "propane", "bird feeder", "battery", "smart lock-never", "ratcheting", "table set", "camp table", "compact table", "1 person", "smoker", "bbq", "pellets", "pellet", "potting", "potting mix", "fertilizer", "bit set", "bit selector", "torx", "screw driver", "screwdriver", "wiha", "multitool", "multi-tool", "cleaver", "fixed blade", "bug zapper", "solar rechargeable", "tool", "tools", "drill", "garden", "grill", "outdoor", "camping", "tent", "screwdriver", "tire", "generator", "electrician", "wrench", "socket", "hammer", "pliers", "crimper", "hex key", "ladder", "power equipment", "lawn", "mower", "backpack", "hiking", "flashlight", "osprey", "daypack", "klein", "gearwrench", "craftsman", "dewalt", "milwaukee", "husky", "makita", "ryobi", "toolbox", "workbench", "pressure washer", "snow blower", "leaf blower", "chainsaw", "welding", "saw", "vacuum lifter", "paint", "hardware"],
    "Grocery & Household": ["steaks", "burgers", "omaha steaks", "bacon", "pork", "chewy treats", "amazon basics liquid", "cheetos", "puffs", "gatorade", "coconut milk", "chili powder", "noodles", "pita", "variety pack", "s&s", "cheddar", "cracker", "crackers", "juice", "soda", "sparkling", "pretzel", "popcorn", "seasoning", "olive oil", "snack", "snacks", "coffee", "chips", "soup", "candy", "chocolate", "paper towel", "paper towels", "toilet paper", "laundry", "detergent", "trash bags", "bottled water", "sparkling water", "tea", "cereal", "pasta", "sauce", "grocery", "gift card", "k-cup", "protein bar", "dish soap", "cleaning wipes", "spread"],
    "Home & Kitchen": ["bar stools", "bar stool", "counter height", "travel bottle", "rambler", "water bottle", "steaks-never", "neon sign", "neon signs", "artificial birch tree", "birch tree", "shower caddy", "barista", "espresso machine", "coffee machine", "trash can", "laundry basket", "hamper", "hangers", "drawer", "closet", "curtain rod", "reverse osmosis", "water filter", "washlet", "bidet", "toilet seat", "steamer", "iron", "sheet sets", "sheet set", "mattress topper", "cookware", "bakeware", "roaster", "frying pan", "noodle-never", "food warming", "warming mat", "couch cover", "glass", "figurine", "kitchen", "kitchenaid", "pan", "pans", "skillet", "cookware", "cook", "cooking", "knife", "knives", "air fryer", "oven", "microwave", "toaster", "blender", "mixer", "instant pot", "pressure cooker", "slow cooker", "coffee maker", "espresso", "kettle", "dinnerware", "plates", "bowls", "mug", "cups", "glassware", "pyrex", "measuring", "tumbler", "water bottle", "cutting board", "oven mitt", "silicone", "storage", "organizer", "vacuum", "robot vacuum", "mop", "cleaner", "mattress", "bedding", "sheet set", "sheets", "pillow", "pillows", "comforter", "blanket", "duvet", "towel", "towels", "rug", "curtain", "curtains", "lamp", "table lamp", "string lights", "led lights", "ceiling fan", "fan", "furniture", "bed frame", "desk", "chair", "sofa", "couch", "shelf", "bookshelf", "step stool", "mat", "mats", "candle", "decor", "wreath", "refrigerator", "fridge", "mini fridge", "freezer", "dishwasher", "washer", "dryer", "humidifier", "air purifier", "heater", "space heater", "fireplace", "hand warmer", "scissors", "fiskars", "cuisinart", "ninja", "keurig", "dyson", "shark", "roborock", "bissell", "home goods"],
}

# retailer/sale words that say nothing about the product itself
_NOISE = re.compile(r"\b(?:home depot|lowe'?s|home goods|best buy|sam'?s club|academy sports(?: & outdoors)?|belk|black friday|early black friday|doorbusters?|lightning deals?|deals?|sale|prime|amazon)\b", re.I)
_CAT_RE = {c: [(w, re.compile(r"(?<![\w'])" + re.escape(w) + r"(?![\w])", re.I)) for w in ws] for c, ws in CATEGORIES.items()}
_BOOST = {"cpu cooler": 4, "avocado oil": 4, "hot sauce": 3, "dog plush": 4, "dog toy": 4, "cat toy": 4, "lip care": 3, "walkie talkie": 4, "walkie talkies": 4, "security system": 3, "security cameras": 3, "christmas": 3, "xmas": 3, "for pets": 4, "baby bottle": 4, "advent": 3}
# on a tie, the more specific category wins
_TIE = ["Holiday & Seasonal", "Baby & Kids", "Toys & Games", "Gaming & Entertainment", "Pets", "Beauty & Health", "Sports & Fitness", "Office & School", "Tech & Electronics",
        "Fashion", "Outdoor & Tools", "Grocery & Household", "Home & Kitchen"]


def store_of(text):
    low = text.lower()
    for s in STORES:
        if s.lower() in low:
            return s
    return "Other"


def is_amazon(d):
    """Amazon deals may only show prices that come from Amazon's own API (Associates policy),
    so for these we never show or say a price, a 'was' price or a % off."""
    store = d.get("store") or store_of(f"{d.get('title', '')} {d.get('desc', '')}")
    return (store == "Amazon" or bool(d.get("asin"))
            or "amazon." in (d.get("link") or "").lower())


PRICE_TEXT_RE = re.compile(
    r"\s*(?:for\s+|from\s+|now\s+|only\s+|just\s+)?\$\s?[\d,]+(?:\.\d+)?\*?"
    r"(?:\s*(?:\+|w/|with)\s*free\s+(?:shipping|s&h|store pickup|delivery))?", re.I)
PCT_OFF_RE = re.compile(r"\s*\(?\b(?:save\s+|up\s+to\s+)?\d+\s?%\s*off\b\)?", re.I)


LEAD_RE = re.compile(r"^\s*(?:\*[A-Za-z ]{2,12}\*\s*)?(?i:(?:amazon\s+)?(?:prime members?|select accounts?|prime)\s*[:\-]\s*)?(?:\[[^\]]*\]\s*)*(?:\$\s?[\d,.]+\*?\s*[:|\-]\s*)?(?:\[[^\]]*\]\s*)*")


def lead_clean(title):
    """'[NEW] $12.59 | PAW Patrol Set' -> 'PAW Patrol Set' (deal-site price/tag prefixes)."""
    t = LEAD_RE.sub("", title or "", count=1).strip()
    return t or title


def no_price_title(title):
    """'Wyze Cam OG for $19.98 + free shipping (40% off)' -> 'Wyze Cam OG'"""
    t = PRICE_TEXT_RE.sub("", lead_clean(title))
    t = PCT_OFF_RE.sub("", t)
    t = re.sub(r"\(\s*\)|\s{2,}", " ", t)
    return t.strip(" -–,|:/+*")


def category_of(text):
    """Score every category by whole-word phrase hits (longer phrase = more weight), best score wins."""
    low = _NOISE.sub(" ", text or "")
    scores = {}
    for cat, pats in _CAT_RE.items():
        n = 0
        for w, rx in pats:
            if rx.search(low):
                n += _BOOST.get(w, 1 + w.count(" "))
        if n:
            scores[cat] = n
    if not scores:
        return "Everything else"
    top = max(scores.values())
    return next(c for c in _TIE if scores.get(c) == top)

KEEP_DAYS = 3          # how long a deal stays on the list
MAX_ROWS = 900         # cap the list (website shows top 100 per category)
DATA_FILE = Path("data/deals.json")
UA = "Mozilla/5.0 (deal-finder; personal RSS reader)"

# Deal blogs that post Amazon/Walmart/Target promo codes. Used only to CROSS-CHECK:
# if the same product shows up there with a code or coupon, we add it to our deal
# (with credit and a link back). Koupon.ai has no public feed, so it isn't here.
CODE_FEEDS = {
    "Hip2Save": "https://hip2save.com/feed/",
    "Fabulessly Frugal": "https://fabulesslyfrugal.com/feed/",
    "Koupon Karen": "https://www.kouponkaren.com/feed/",
    "The Freebie Guy": "https://thefreebieguy.com/feed/",
    "Passionate Penny Pincher": "https://passionatepennypincher.com/feed/",
    "9to5Toys": "https://9to5toys.com/feed/",
}

PRICE_RE = re.compile(r"\$\s?(\d[\d,]*(?:\.\d{2})?)")
# Real promo codes are written in capitals, e.g. "code: SAVE50XY". The word
# "code" is matched in any case, the code itself only in capitals/digits,
# so seller names like "w/ Code Sunway Direct" are not mistaken for codes.
CODE_RE = re.compile(r"(?i:code|coupon)[:\s]+[\"']?([A-Z0-9]{4,20})\b")
TAG_RE = re.compile(r"<[^>]+>")
ASIN_RE = re.compile(r"amazon\.com/(?:[^\s\"'<>]*?/)?(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})")
CAMEL_RE = re.compile(r"(.+?) - down ([\d.]+)% \(\$[\d,.]+\) to \$([\d,]+\.\d{2}) from \$([\d,]+\.\d{2})")
CAMEL_MAX_PRICE = float(os.environ.get("CAMEL_MAX_PRICE") or "150")
CAMEL_MIN_DROP = float(os.environ.get("CAMEL_MIN_DROP") or "20")
HISTORY_FILE = Path("data/price_history.json")
THUMBS_RE = re.compile(r"thumb score:\s*\+?(\d+)", re.I)
# Words that mean a deal or code is dead. A code found next to these is never shown.
EXPIRED_RE = re.compile(r"\b(expired|has ended|deal ended|ended|no longer (?:available|valid|working)|"
                        r"sold out|out of stock|(?:code|coupon) (?:is )?(?:not working|doesn'?t work|invalid|maxed))\b", re.I)
TESTED_FILE = Path("data/tested.json")
WAS_RE = re.compile(r"(?:list price|reg(?:ularly)?\.?|was|originally|retail|typically|normally)\s*:?\s*\$\s?(\d[\d,]*(?:\.\d{2})?)", re.I)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def clean(text):
    return html.unescape(TAG_RE.sub(" ", text or "")).replace("\xa0", " ").strip()


def features_from(raw_html):
    """Bullet points (<li>) from the deal's own description: real product features."""
    items = re.findall(r"<li[^>]*>(.*?)</li>", raw_html or "", re.I | re.S)
    feats = []
    for it in items:
        t = re.sub(r"\s+", " ", clean(it))
        if 6 <= len(t) <= 80 and "$" not in t and "http" not in t.lower():
            feats.append(t)
    return feats[:3]


ASIN_MAP = json.loads(Path('data/asin_map.json').read_text()) if Path('data/asin_map.json').exists() else {}   # made by amazon_local.py on the home PC
HIP_CACHE = Path("data/hip2save_asin.json")
_hip = json.loads(HIP_CACHE.read_text()) if HIP_CACHE.exists() else {}
_hip_budget = [30]                                        # page fetches per run


def hip_asin(link):
    """Amazon product ID behind a Hip2Save post (cached; they link to Amazon inside the post)."""
    if link in _hip:
        return _hip[link]
    if _hip_budget[0] <= 0:
        return ""
    _hip_budget[0] -= 1
    try:
        page = urllib.parse.unquote(urllib.parse.unquote(html.unescape(fetch(link).decode('utf8', 'ignore'))))
        m = ASIN_RE.search(page) or re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", page)
        if m:
            _hip[link] = m.group(1)                 # only successes are cached; failures retry next run
    except Exception as e:
        print(f"[warn] hip2save page {link}: {e}")
    return _hip.get(link, "")


def parse_feed(source, raw):
    """Return a list of deal dicts from one RSS feed."""
    deals = []
    root = ET.fromstring(raw)
    for item in root.iter("item"):
        if source.startswith("Hip2Save") and not any((c.text or "") == "Amazon" for c in item.findall("category")):
            continue
        title = clean(item.findtext("title"))
        link = (item.findtext("link") or "").strip()
        raw_desc = item.findtext("description") or ""
        cc = CAMEL_RE.match(title) if "camelcamelcamel.com/product/" in link else None
        if cc:
            # Price-drop feed of ALL Amazon products. Keep only family-size prices and real drops.
            now_p, was_p = (float(cc.group(i).replace(",", "")) for i in (3, 4))
            if now_p > CAMEL_MAX_PRICE or float(cc.group(2)) < CAMEL_MIN_DROP:
                continue
            title = f"{cc.group(1).strip()} - ${cc.group(3)} (was ${cc.group(4)}, down {cc.group(2)}%)"
            raw_desc = f"List price: ${cc.group(4)}. Amazon price drop. {link}"
            link = link.replace("camelcamelcamel.com/product/", "www.amazon.com/dp/")
        # Slickdeals puts the full text in content:encoded
        for child in item:
            if child.tag.endswith("encoded") and child.text:
                raw_desc = child.text
        image = ""
        m_img = re.search(r'<img[^>]+src="([^"]+)"', raw_desc)
        if m_img:
            image = html.unescape(m_img.group(1))
        for child in item:                       # DealNews: <media:thumbnail url=...> / <media:content url=...>
            if not image and child.tag.endswith(("thumbnail", "content")) and child.get("url"):
                image = child.get("url")
        if source.startswith("Hip2Save"):
            for child in item:
                if child.tag.endswith("thumbnail-image") and child.text:
                    image = child.text.split("?")[0]               # full-size upload, not the 306px crop
        desc = re.sub(r"\s+", " ", clean(raw_desc))
        blob = f"{title} {desc}".lower()
        try:
            when = parsedate_to_datetime(item.findtext("pubDate")).astimezone(timezone.utc)
        except Exception:
            when = datetime.now(timezone.utc)
        price = PRICE_RE.search(title)
        code = CODE_RE.search(f"{title} {desc}")
        thumbs = THUMBS_RE.search(desc)
        # Deal sites wrap Amazon links in encoded redirects (amazon.com%2Fdp%2F...),
        # so decode twice before looking for the product ID.
        decoded = urllib.parse.unquote(urllib.parse.unquote(html.unescape(raw_desc + " " + link)))
        asin = ASIN_RE.search(decoded)
        if not asin and source.startswith("Hip2Save"):
            asin = re.match(r"(.+)", hip_asin(link) or "")
        was = WAS_RE.search(f"{title} {desc}")
        deals.append({
            "id": link or title,
            "title": title,
            "price": f"${price.group(1)}" if price else "",
            "code": code.group(1).upper() if code else ("w/ code" if "w/ code" in blob or "promo code" in blob else ""),
            "coupon": "clip coupon" if "clip" in blob and "coupon" in blob else "",
            "asin": asin.group(1) if asin else ASIN_MAP.get(link, ""),
            "store": store_of(f"{title} {desc}"),
            "category": category_of(title),
            "thumbs": int(thumbs.group(1)) if thumbs else 0,
            "was": f"${was.group(1)}" if was else "",
            "features": features_from(raw_desc),
            "new": bool(re.search(r"\b(new release|newly released|just launched|new arrival|2026 model)\b", blob)),
            "bestseller": bool(re.search(r"\b(best ?seller|#1 best)", blob)),
            "expired": bool(EXPIRED_RE.search(blob)),
            "desc": desc[:500],
            "source": source,
            "image": image,
            "link": link,
            "seen": when.isoformat(),
        })
    return deals


def product_key(d):
    """ASIN when we have it, else a simplified product name."""
    if d.get("asin"):
        return d["asin"]
    name = re.split(r"\s+(?:for\s+)?\$\d", d["title"].lower())[0]
    return re.sub(r"[^a-z0-9 ]", "", name).strip()[:60]


def update_price_history(new):
    hist = json.loads(HISTORY_FILE.read_text()) if HISTORY_FILE.exists() else {}
    for d in new:
        p = PRICE_RE.search(d.get("price", "") or "")
        if not p:
            continue
        value = float(p.group(1).replace(",", ""))
        day = d["seen"][:10]
        rows = hist.setdefault(product_key(d), [])
        if not any(r[0] == day and r[1] == value for r in rows):
            rows.append([day, value])
        rows.sort()
        del rows[:-60]                      # keep the last 60 price points
    HISTORY_FILE.write_text(json.dumps(hist))
    return hist


def load_history():
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text())
    return []


STOP = {"with", "from", "for", "and", "the", "pack", "pcs", "piece", "free", "shipping", "amazon",
        "deal", "deals", "code", "coupon", "promo", "save", "off", "only", "just", "now", "new",
        "this", "that", "your", "women", "womens", "men", "mens", "kids", "set"}


def name_words(title):
    t = re.sub(r"[^a-z0-9 ]+", " ", no_price_title(title).lower())
    return {w for w in t.split() if len(w) >= 4 and w not in STOP and not w.isdigit()}


def cross_check(deals, extras):
    """Attach codes/coupons found for the same product on other deal sites.
    Match on Amazon product ID, or on at least 4 shared product-name words
    that make up most of the shorter name (strict, to avoid wrong codes)."""
    useful = [e for e in extras
              if ((e["code"] and e["code"] != "w/ code") or e["coupon"]) and not e.get("expired")]
    for e in useful:
        e["_words"] = name_words(e["title"])
    for d in deals:
        words = name_words(d["title"])
        found = []
        for e in useful:
            same_asin = d.get("asin") and d["asin"] == e.get("asin")
            shared = words & e["_words"]
            close = len(shared) >= 4 and len(shared) >= 0.7 * min(len(words), len(e["_words"]))
            if not (same_asin or close):
                continue
            item = {"source": e["source"], "link": e["link"], "code": e["code"] if e["code"] != "w/ code" else "",
                    "coupon": bool(e["coupon"]), "by_id": bool(same_asin), "seen": e["seen"]}
            if item["code"] == d.get("code") and not item["coupon"]:
                continue                     # same code we already show
            if not any(f["source"] == item["source"] and f["code"] == item["code"] for f in found):
                found.append(item)
        old = [f for f in d.get("also", []) if not any(f["source"] == n["source"] and f["code"] == n["code"] for n in found)]
        if found or old:
            d["also"] = (found + old)[:3]
        # a code confirmed by product ID fills in a missing code
        if (not d.get("code") or d["code"] == "w/ code"):
            sure = next((f for f in found if f["by_id"] and f["code"]), None)
            if sure:
                d["code"], d["code_from"] = sure["code"], sure["source"]
        if not d.get("coupon") and any(f["by_id"] and f["coupon"] for f in found):
            d["coupon"] = "clip coupon"
    return deals


def score_codes(deals):
    """Give every deal with a code or coupon a confidence score and label.
    Fresh + confirmed by other sites + tested by you = high. Old or 'expired' wording = low.
    This is a guess from the data, NOT a live check: test in the cart before you post."""
    tested = json.loads(TESTED_FILE.read_text()) if TESTED_FILE.exists() else {}
    now = datetime.now(timezone.utc)
    today = now.strftime("%b %d")
    for d in deals:
        has_code = bool(d.get("code") and d["code"] != "w/ code")
        if not (has_code or d.get("coupon")):
            d.pop("code_score", None); d.pop("code_label", None)
            continue
        if d.get("expired"):
            d["code_score"], d["code_label"] = 0, "expired"
            continue
        age_h = (now - datetime.fromisoformat(d["seen"])).total_seconds() / 3600
        score = 50 + (30 if age_h < 6 else 20 if age_h < 24 else 5 if age_h < 48 else -20)
        agree = [f for f in d.get("also", []) if (f["code"] and f["code"] == d.get("code")) or (f["coupon"] and d.get("coupon"))]
        score += 15 * min(len(agree), 2)
        if d.get("thumbs", 0) >= 50:
            score += 10
        t = tested.get(d["id"])
        if t:
            score += 40 if t.get("date") == today else 15
        d["code_score"] = max(0, min(100, score))
        d["code_label"] = "likely works" if score >= 70 else "check first" if score >= 40 else "may be expired"
    return deals


def merge(history, new):
    by_id = {d["id"]: d for d in history}
    seen_titles = {d["title"].lower() for d in history}
    for d in new:
        if d["id"] in by_id or d["title"].lower() in seen_titles:
            continue
        by_id[d["id"]] = d
        seen_titles.add(d["title"].lower())
    cutoff = datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)
    kept = [d for d in by_id.values() if datetime.fromisoformat(d["seen"]) >= cutoff]
    kept.sort(key=lambda d: d["seen"], reverse=True)
    return kept[:MAX_ROWS]


def write_markdown(deals, errors):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Mom Found It Cheaper - deal list",
        "",
        f"Updated {now} - {len(deals)} deals from the last {KEEP_DAYS} days, newest first.",
        "",
        "> Before posting: open the deal, check the price is real, then make **your own SiteStripe link**. "
        "Never repost the source link. Add #ad.",
        "",
        "| Found | Deal | Price | Code / coupon | Source |",
        "|---|---|---|---|---|",
    ]
    for d in deals:
        when = datetime.fromisoformat(d["seen"]).strftime("%b %d %H:%M")
        title = d["title"].replace("|", "/")
        extra = " / ".join(x for x in (d["code"], d["coupon"]) if x)
        if extra and d.get("code_label"):
            extra += f" ({d['code_label']})"
        lines.append(f"| {when} | [{title}]({d['link']}) | {d['price']} | {extra} | {d['source']} |")
    if errors:
        lines += ["", "Feeds that failed this run: " + ", ".join(errors)]
    lines += ["", "Deal data from Slickdeals and DealNews RSS feeds, for personal use."]
    Path("DEALS.md").write_text("\n".join(lines) + "\n")


def write_html(deals):
    rows = []
    for d in deals:
        when = datetime.fromisoformat(d["seen"]).strftime("%b %d %H:%M")
        extra = " / ".join(x for x in (d["code"], d["coupon"]) if x)
        rows.append(
            f"<tr><td>{when}</td><td><a href='{html.escape(d['link'])}'>{html.escape(d['title'])}</a></td>"
            f"<td>{html.escape(d['price'])}</td><td>{html.escape(extra)}</td><td>{html.escape(d['source'])}</td></tr>"
        )
    page = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mom Found It Cheaper - deals</title>
<style>body{{font-family:system-ui,sans-serif;margin:12px}}table{{border-collapse:collapse;width:100%}}
td,th{{border-bottom:1px solid #ddd;padding:6px;font-size:14px;text-align:left;vertical-align:top}}
th{{background:#f4f4f4}}a{{color:#0a58ca}}</style></head><body>
<h2>Mom Found It Cheaper - Amazon deals</h2>
<p>{len(deals)} deals, newest first. Make your own SiteStripe link before posting.</p>
<table><tr><th>Found</th><th>Deal</th><th>Price</th><th>Code / coupon</th><th>Source</th></tr>
{''.join(rows)}</table><p>Data: Slickdeals and DealNews RSS feeds.</p></body></html>"""
    Path("deals.html").write_text(page)


def main():
    new, errors = [], []
    for name, url in FEEDS.items():
        try:
            new += parse_feed(name, fetch(url))
        except Exception as e:  # one bad feed should not stop the rest
            errors.append(name)
            print(f"[warn] {name}: {e}")
    extras, status = [], {}
    for name, url in CODE_FEEDS.items():
        try:
            items = parse_feed(name, fetch(url))
            extras += items
            status[name] = {"items": len(items),
                            "with_code_or_coupon": sum(1 for i in items if (i["code"] and i["code"] != "w/ code") or i["coupon"])}
        except Exception as e:
            print(f"[warn] code feed {name}: {e}")
            status[name] = {"error": str(e)[:120]}
    DATA_FILE.parent.mkdir(exist_ok=True)
    update_price_history(new)
    deals = score_codes(cross_check(merge(load_history(), new), extras))
    status["_matched_deals"] = sum(1 for d in deals if d.get("also"))
    Path("data/code_feeds.json").write_text(json.dumps(status, indent=1))
    for _d in deals:                                  # IDs the home PC found (older records keep their empty asin otherwise)
        if not _d.get("asin") and ASIN_MAP.get(_d["id"]):
            _d["asin"] = ASIN_MAP[_d["id"]]
    DATA_FILE.write_text(json.dumps(deals, indent=1))
    HIP_CACHE.write_text(json.dumps(_hip, indent=1))
    write_markdown(deals, errors)
    write_html(deals)
    print(f"{len(new)} deals fetched, {len(deals)} on the list, {len(errors)} feeds failed")


if __name__ == "__main__":
    main()
