"""Daily approval queue (no tokens). Collects everything that passed QA today plus a few
engagement drafts, and writes queue/QUEUE.md. The videos workflow turns that file into a
GitHub issue so Rohini can approve by comment ("post 1, 3, q2") from her phone.
Nothing here posts anything.

Run after make_posts.py / post_qa.py:  python make_queue.py
"""
import html
import json
import random
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "queue"
SITE = "https://momfounditcheaper.com/"
DISCLOSURE = "As an Amazon Associate I earn from qualifying purchases. #ad"


def passed_posts():
    """Post ids that POST_QA.md marks ok (strict gate output)."""
    qa = (ROOT / "POST_QA.md").read_text() if (ROOT / "POST_QA.md").exists() else ""
    ok = []
    for m in re.finditer(r"^## (post_\w+) \(([^)]*)\): (ok[^\n]*)", qa, re.M):
        ok.append((m.group(1), m.group(2), m.group(3)))
    return ok


def caption_for(pid):
    for d in ("posts", "webposts"):
        f = ROOT / d / f"{pid}.txt"
        if f.exists():
            return f.read_text().strip()
    return ""


def videos_today():
    return sorted(p.name for p in (ROOT / "videos").glob("deal_*.mp4")) if (ROOT / "videos").exists() else []


def tier_posts():
    """One ready-to-paste Facebook post per price tier: 5 verified items + a link to that tier on the site.
    Built from the live site HTML so it can never list something the site gate rejected."""
    html_ = (ROOT / "site" / "index.html").read_text() if (ROOT / "site" / "index.html").exists() else ""
    out = []
    for key, label in (("under-10", "Under $10"), ("under-20", "Under $20"), ("under-25", "Under $25"), ("under-50", "Under $50")):
        m = re.search(r'<section class="tier-sec" id="%s">(.*?)</section>' % key, html_, re.S)
        if not m:
            continue
        titles = [html.unescape(t) for t in re.findall(r"<h3>([^<]+)</h3>", m.group(1))][:5]
        if len(titles) < 3:
            continue
        lines = "\n".join(f"{i}. {t}" for i, t in enumerate(titles, 1))
        out.append({"tier": label, "text": f"{label} finds today (every link checked against Amazon this morning):\n{lines}\n\n"
                                           f"All of them, with links: {SITE}#{key}\n{DISCLOSURE}"})
    return out


def engagement_drafts(day):
    """Short, honest engagement posts. Rotates by weekday so the Page never repeats itself."""
    rnd = random.Random(day.toordinal())
    polls = [
        ("Which would you grab first?", ["Kitchen gadget", "Kids' toy", "Cozy home find", "Beauty steal"]),
        ("What's your Black Friday budget this year?", ["Under $50", "$50-150", "$150-300", "No limit, help me"]),
        ("Best stocking stuffer price?", ["Under $5", "$5-10", "$10-20", "Price doesn't matter if it's cute"]),
        ("Where do you shop most?", ["Amazon", "Walmart", "Target", "Costco"]),
    ]
    q, opts = rnd.choice(polls)
    asks = [
        "Drop one thing you're hunting for this week and I'll go find it cheaper. 👇",
        "Deal or dud? Comment DEAL if you'd buy today's top find, DUD if you'd pass.",
        "Moms: what's the one thing you overpaid for last year? I'll find a better price.",
        "Tell me your kid's age and I'll post three gift finds under $20 for that age.",
    ]
    return [
        {"type": "poll", "text": q, "options": opts},
        {"type": "ask", "text": rnd.choice(asks)},
        {"type": "pin", "text": f"New here? Every deal on {SITE} is checked by hand before it's posted. "
                                f"Save the page, turn on notifications, and comment what you want found cheaper. {DISCLOSURE}"},
    ]


def main():
    OUT.mkdir(exist_ok=True)
    day = datetime.now(timezone.utc)
    posts = passed_posts()
    vids = videos_today()
    eng = engagement_drafts(day)
    lines = [f"# Approval queue — {day:%Y-%m-%d}", "",
             "Reply with the numbers to approve, e.g. `post 1, q2; video 3; eng poll`. Nothing is posted until you say so.", "",
             f"## Posts that passed strict QA ({len(posts)})"]
    for pid, theme, status in posts:
        cap = caption_for(pid)
        lines += [f"### {pid} — {theme} ({status})", "```", cap[:900], "```", ""]
    lines += [f"## Videos ({len(vids)})"] + [f"- {v}  (caption: videos/{v[:-4]}.txt)" for v in vids] + [""]
    tiers = tier_posts()
    lines += [f"## Price-tier posts for the Page ({len(tiers)})"]
    for tp in tiers:
        lines += [f"### {tp['tier']}", "```", tp["text"], "```", ""]
    pins_dir = sorted((ROOT / "pins").glob("*/")) if (ROOT / "pins").exists() else []
    if pins_dir:
        pn = sorted(p.name for p in pins_dir[-1].glob("pin_*.png"))
        lines += [f"## Pinterest pins ({len(pn)}) — folder pins/{pins_dir[-1].name}/ (pins.csv has title, description, link)"] + [f"- {n}" for n in pn] + [""]
    lines += ["## Engagement drafts (Page)"]
    for e in eng:
        if e["type"] == "poll":
            lines += [f"- **Poll:** {e['text']}  Options: {' / '.join(e['options'])}"]
        else:
            lines += [f"- **{e['type'].title()}:** {e['text']}"]
    lines += ["", "## Checklist before posting",
              "- Group status confirmed restored; Page posting only until then",
              "- Link goes to momfounditcheaper.com (not a raw amazon.com link) unless tagged via Meta Affiliate Partnerships",
              f"- Disclosure in every post: {DISCLOSURE}",
              "- Price re-checked on Amazon at posting time"]
    (OUT / "QUEUE.md").write_text("\n".join(lines))
    (OUT / "queue.json").write_text(json.dumps({"date": f"{day:%Y-%m-%d}", "posts": [p[0] for p in posts],
                                                 "videos": vids, "engagement": eng, "tier_posts": tiers}, indent=1))
    print(f"queue: {len(posts)} posts, {len(vids)} videos, {len(eng)} engagement drafts -> queue/QUEUE.md")


if __name__ == "__main__":
    main()
