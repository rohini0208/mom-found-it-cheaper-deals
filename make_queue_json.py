#!/usr/bin/env python3
"""Emit queue/<ET-date>.json: one machine-readable record per item (pin / post / reel) for the
approval dashboard and the n8n publisher. Every item carries a PUBLIC preview URL (the exact image
or video a viewer sees), the caption, the destination link, a QA block (filled by qa_free.py), and a
status. No tokens: this runs in CI next to the render.

Served at https://momfounditcheaper.com/queue/<date>.json (build_site copies queue/*.json)."""
import utf8_io  # noqa: F401  (first import: forces UTF-8 text IO so Windows cp1252 can't crash on emoji)
import csv
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SITE = "https://momfounditcheaper.com"
REPO = "rohini0208/mom-found-it-cheaper-deals"
REL = f"https://github.com/{REPO}/releases/download/todays-videos"   # public release asset URLs
ET = ZoneInfo("America/New_York")


def _date():
    return datetime.now(ET).strftime("%Y-%m-%d")


def _read(p):
    try:
        return Path(p).read_text(encoding="utf-8")
    except Exception:
        return ""


def _split_caption(txt):
    """FB/Pinterest caption vs the link that belongs in the first comment (Smart Savers pattern)."""
    txt = txt.strip()
    m = re.search(r"(https?://\S+)", txt)
    link = m.group(1) if m else ""
    # the comment is the disclosure + link line; the post body is the rest
    lines = [l for l in txt.splitlines() if l.strip()]
    body = "\n".join(l for l in lines if "http" not in l).strip()
    comment = next((l for l in lines if "http" in l), (f"#ad Shop here (prices change): {link}" if link else ""))
    return body, comment, link


def build(date):
    pins, posts, reels = [], [], []

    # --- pins (from the Pinterest CSV) ---
    pd = Path("pins") / date
    csvf = pd / "pins.csv"
    if csvf.exists():
        for i, r in enumerate(csv.DictReader(open(csvf, encoding="utf-8")), 1):
            pins.append({
                "id": f"pin_{i:02d}",
                "type": "pin",
                "title": r.get("Title", ""),
                "caption": r.get("Description", ""),
                "image_url": r.get("Media URL", ""),
                "link": r.get("Link", ""),
                "board": r.get("Pinterest board", ""),
                "qa": {"status": "pending", "models": []},
                "status": "pending",
            })

    # --- posts (webposts images + captions from posts/<file>.txt) ---
    for img in sorted(Path("webposts").glob("post_*.png")):
        name = img.stem                                   # post_1, post_q3, post_single
        cap = _read(Path("posts") / f"{name}.txt")
        body, comment, link = _split_caption(cap)
        posts.append({
            "id": name,
            "type": "post",
            "title": (body.splitlines() or [name])[0][:80],
            "caption": body,
            "comment": comment,                            # link goes in the first comment, not the post body
            "image_url": f"{SITE}/posts/{img.name}",
            "link": link,
            "qa": {"status": "pending", "models": []},
            "status": "pending",
        })

    # --- reels (public release MP4s + captions) ---
    for n in range(1, 40):
        cap = _read(f"deal_{n}.txt") or _read(Path("videos") / f"deal_{n}.txt")
        mp4_local = Path("videos") / f"deal_{n}.mp4"
        # include if we have a caption or the local render (CI lists the release separately)
        if not cap and not mp4_local.exists():
            continue
        body, comment, link = _split_caption(cap)
        reels.append({
            "id": f"deal_{n}",
            "type": "reel",
            "title": (body.splitlines() or [f"Reel {n}"])[0][:80],
            "caption": body,
            "video_url": f"{REL}/deal_{n}.mp4",
            "link": link,
            "qa": {"status": "pending", "models": []},
            "status": "pending",
        })

    return {
        "date": date,
        "generated": datetime.now(ET).isoformat(timespec="seconds"),
        "counts": {"pins": len(pins), "posts": len(posts), "reels": len(reels)},
        "pins": pins,
        "posts": posts,
        "reels": reels,
    }


def main():
    date = _date()
    q = build(date)
    out = Path("queue")
    out.mkdir(exist_ok=True)
    (out / f"{date}.json").write_text(json.dumps(q, indent=2), encoding="utf-8")
    (out / "latest.json").write_text(json.dumps(q, indent=2), encoding="utf-8")   # dashboard default
    print(f"queue/{date}.json: {q['counts']}")


if __name__ == "__main__":
    main()
