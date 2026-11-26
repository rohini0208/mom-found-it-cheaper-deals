"""Unlisted review page: everything in today's approval queue, with images and full captions, on one page.
Writes site/review.html (not linked from the site; robots noindex). Run after make_queue.py:  python make_review.py
"""
import html
import json
import re
import shutil
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "site"


def esc(t):
    return html.escape(t or "")


def main():
    q = json.loads((ROOT / "queue" / "queue.json").read_text())
    day = q.get("date", date.today().isoformat())
    (OUT / "review").mkdir(parents=True, exist_ok=True)
    parts = []
    # posts
    parts.append(f"<h2>Facebook posts that passed strict QA ({len(q['posts'])})</h2>")
    for pid in q["posts"]:
        png = ROOT / "webposts" / f"{pid}.png"            # webposts/ is committed; posts/ is not
        if not png.exists():
            png = ROOT / "posts" / f"{pid}.png"
        if png.exists():
            shutil.copy(png, OUT / "review" / png.name)
        cap = q.get("captions", {}).get(pid, "")
        parts.append(f'<section class="item"><h3>{esc(pid)}</h3>'
                     f'{f"<img src=review/{png.name} loading=lazy>" if png.exists() else "<p><em>no image</em></p>"}'
                     f'<pre>{esc(cap)}</pre></section>')
    # tier posts
    parts.append(f"<h2>Price-tier posts for the Page ({len(q.get('tier_posts', []))})</h2>")
    for tp in q.get("tier_posts", []):
        parts.append(f'<section class="item"><h3>{esc(tp["tier"])}</h3><pre>{esc(tp["text"])}</pre></section>')
    # pins
    pin_dirs = sorted((ROOT / "pins").glob("*/"))
    if pin_dirs:
        pd = pin_dirs[-1]
        rows = []
        try:
            import csv
            rows = list(csv.DictReader(open(pd / "pins.csv")))
        except Exception:
            pass
        parts.append(f"<h2>Pinterest pins ({len(rows)})</h2><div class=grid>")
        for r in rows:
            src = pd / r["media_url"]
            if src.exists():
                shutil.copy(src, OUT / "review" / src.name)
            parts.append(f'<section class="item pin"><img src=review/{esc(r["media_url"])} loading=lazy>'
                         f'<pre><b>Title:</b> {esc(r["title"])}\n<b>Link:</b> {esc(r["link"])}\n<b>Description:</b> {esc(r["description"])}</pre></section>')
        parts.append("</div>")
    # videos
    parts.append(f"<h2>Videos ({len(q['videos'])})</h2>")
    for v in q["videos"]:
        src = ROOT / "videos" / v
        if src.exists():
            shutil.copy(src, OUT / "review" / v)
        parts.append(f'<section class="item"><h3>{esc(v)}</h3>'
                     f'{f"<video src=review/{v} controls preload=none width=270></video>" if src.exists() else "<p><em>video file is in the daily release, not on the site</em></p>"}'
                     f'<pre>{esc(q.get("video_captions", {}).get(v, ""))}</pre></section>')
    # engagement
    parts.append("<h2>Engagement drafts</h2>")
    for e in q.get("engagement", []):
        body = e["text"] + ("\n  Options: " + " / ".join(e["options"]) if e.get("options") else "")
        parts.append(f'<section class="item"><h3>{esc(e["type"])}</h3><pre>{esc(body)}</pre></section>')
    page = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<meta name=robots content="noindex,nofollow"><title>Review queue {esc(day)} - Mom Found It Cheaper</title>
<style>body{{font-family:Inter,system-ui,sans-serif;background:#FFF6EC;color:#1F1A2E;margin:0;padding:20px;max-width:1100px;margin:auto}}
h1{{font-size:28px}}h2{{margin-top:36px;border-bottom:2px solid #1F1A2E;padding-bottom:6px}}
.item{{background:#fff;border-radius:18px;padding:16px;margin:14px 0;display:grid;grid-template-columns:320px 1fr;gap:16px;align-items:start}}
.item img,.item video{{width:100%;border-radius:12px;border:1px solid #eee}}.pin img{{max-width:320px}}
pre{{white-space:pre-wrap;font:14px/1.5 Inter,system-ui,sans-serif;margin:0;color:#2b2540}}
.grid{{display:grid;grid-template-columns:1fr;gap:0}}.note{{background:#FFC53D;padding:10px 14px;border-radius:12px;font-weight:700;display:inline-block}}
@media(max-width:700px){{.item{{grid-template-columns:1fr}}}}</style></head><body>
<h1>Review queue - {esc(day)}</h1><p class=note>Nothing on this page has been posted. Reply in the GitHub approval issue (or to Claude) with what to post.</p>
{''.join(parts)}
</body></html>"""
    (OUT / "review.html").write_text(page)
    print(f"review page: {len(q['posts'])} posts, {len(q.get('tier_posts', []))} tier posts, {len(q['videos'])} videos -> site/review.html")


if __name__ == "__main__":
    main()
