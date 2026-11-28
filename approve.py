#!/usr/bin/env python3
"""Approve / reject queue items without hand-editing JSON.

The posters (pinterest_ui_post.py, pinterest_post.py) only publish items whose status is
"approved" and whose QA is not "fail". This sets that status in queue/latest.json (and the
matching dated file). Running it IS your approval - nothing auto-approves.

List everything (id, type, judge score, QA, status):
    python approve.py

Approve specific items by id (any type):
    python approve.py pin_01 pin_03 post_2

Approve in bulk (only items whose QA is not "fail"):
    python approve.py --all                 # every pin/post/reel that passed QA
    python approve.py --all --pins          # only pins
    python approve.py --all --min-judge 7   # only those the judge scored >= 7

Reject (will not be posted):
    python approve.py --reject pin_05
"""
import utf8_io  # noqa: F401  (first import: forces UTF-8 text IO so Windows cp1252 can't crash on emoji)
import argparse
import json
from pathlib import Path

GROUPS = ("pins", "posts", "reels")
LATEST = Path("queue/latest.json")


def _load():
    if not LATEST.exists():
        raise SystemExit("queue/latest.json not found - run the pipeline first.")
    return json.loads(LATEST.read_text())


def _save(q):
    LATEST.write_text(json.dumps(q, indent=2))
    date = q.get("date")
    if date:
        dated = Path("queue") / f"{date}.json"
        if dated.exists():
            dated.write_text(json.dumps(q, indent=2))


def _iter(q):
    for g in GROUPS:
        for it in q.get(g, []):
            yield g, it


def show(q):
    print(f"{'id':12} {'type':5} {'judge':5} {'qa':5} status")
    print("-" * 44)
    for g, it in _iter(q):
        j = (it.get("judge") or {}).get("score")
        qa = (it.get("qa") or {}).get("status", "-")
        print(f"{it.get('id',''):12} {it.get('type',''):5} {str(j):5} {qa:5} {it.get('status','pending')}")
    n = {g: len(q.get(g, [])) for g in GROUPS}
    appr = sum(1 for _, it in _iter(q) if it.get("status") == "approved")
    print(f"\n{n['pins']} pins, {n['posts']} posts, {n['reels']} reels  |  {appr} approved")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*", help="item ids to approve")
    ap.add_argument("--all", action="store_true", help="approve all items whose QA is not fail")
    ap.add_argument("--pins", action="store_true", help="limit --all to pins")
    ap.add_argument("--posts", action="store_true", help="limit --all to posts")
    ap.add_argument("--reels", action="store_true", help="limit --all to reels")
    ap.add_argument("--min-judge", type=float, default=None, help="with --all, require judge score >= this")
    ap.add_argument("--reject", nargs="+", default=[], help="item ids to reject")
    a = ap.parse_args()
    q = _load()

    if not a.ids and not a.all and not a.reject:
        show(q)
        return

    scope = [g for g, flag in (("pins", a.pins), ("posts", a.posts), ("reels", a.reels)) if flag] or list(GROUPS)
    changed = []

    if a.all:
        for g, it in _iter(q):
            if g not in scope:
                continue
            if (it.get("qa") or {}).get("status") == "fail":
                continue
            if a.min_judge is not None:
                js = (it.get("judge") or {}).get("score")
                if js is None or js < a.min_judge:
                    continue
            it["status"] = "approved"; changed.append(it["id"])

    for want in a.ids:
        for _, it in _iter(q):
            if it.get("id") == want:
                if (it.get("qa") or {}).get("status") == "fail":
                    print(f"skip {want}: QA failed (not approvable)")
                else:
                    it["status"] = "approved"; changed.append(want)
                break
        else:
            print(f"not found: {want}")

    for want in a.reject:
        for _, it in _iter(q):
            if it.get("id") == want:
                it["status"] = "rejected"; changed.append(f"-{want}")
                break
        else:
            print(f"not found: {want}")

    _save(q)
    approved = [c for c in changed if not c.startswith("-")]
    rejected = [c[1:] for c in changed if c.startswith("-")]
    if approved:
        print(f"approved ({len(approved)}): {', '.join(sorted(set(approved)))}")
    if rejected:
        print(f"rejected ({len(rejected)}): {', '.join(sorted(set(rejected)))}")
    if not changed:
        print("no changes")


if __name__ == "__main__":
    main()
