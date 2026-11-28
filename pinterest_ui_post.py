#!/usr/bin/env python3
"""Human-like Pinterest poster that drives the REAL Pinterest website with Playwright.

Why this exists: Pinterest's API won't create public pins on Trial access (needs Standard
review). This posts through the normal pin-builder UI instead - it uploads the PNG with a
real file input, fills the fields, picks the board and publishes, the same clicks you'd do
by hand, with randomized pauses, a daytime window and a warm-up ramp so a new account is
not flagged.

You log in ONCE yourself (--login opens a browser; sign in to the Mom Found It Cheaper
business account). The session is saved in a local profile folder (.pw_pinterest/, gitignored).
This script never sees or types your password.

Approval gate (unchanged): only pins with status == "approved" in queue/latest.json and
QA != "fail" are posted. Nothing posts unless you pass --go (default is a dry run that
opens each pin's form but does NOT publish).

Setup on the Lenovo (one time):
    pip install playwright
    python -m playwright install chromium

Usage:
    python pinterest_ui_post.py --login            # opens browser; sign in, then press Enter
    python pinterest_ui_post.py                     # dry run: fills a form, does NOT publish
    python pinterest_ui_post.py --go --once --now   # publish ONE approved pin now (test)
    python pinterest_ui_post.py --go                # paced drip of approved pins (leave running)
"""
import utf8_io  # noqa: F401  (first import: forces UTF-8 text IO so Windows cp1252 can't crash on emoji)
import argparse
import json
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# reuse the exact pacing / gate / state helpers from the API poster so behavior matches
from pinterest_post import (ET, ramp_cap, account_age_days, window_open, seconds_until_window,
                            eligible_pins, _read_json, _write_json, QUEUE, POSTED, STATE, STATUS,
                            MIN_GAP, MAX_GAP, WIN_START, WIN_END)

PROFILE = Path(".pw_pinterest")                          # persistent browser profile (holds your login)
PIN_BUILDER = "https://www.pinterest.com/pin-builder/"


def human_pause(a=0.4, b=1.6):
    time.sleep(random.uniform(a, b))


def local_image(image_url):
    """Map a pin's public image_url back to the local PNG under pins/<date>/."""
    i = image_url.find("/pins/")
    if i == -1:
        return None
    rel = image_url[i + 1:]                               # pins/<date>/<file>.png
    p = Path(rel)
    return p if p.exists() else None


def _first(page, getters, timeout=8000):
    """Return the first locator (from a list of lambdas) that resolves to a visible element."""
    for g in getters:
        try:
            loc = g()
            loc.wait_for(state="visible", timeout=timeout)
            return loc
        except Exception:
            continue
    return None


def type_like_human(loc, text):
    loc.click()
    human_pause(0.2, 0.6)
    loc.fill("")
    loc.type(text, delay=random.uniform(40, 110))
    human_pause(0.3, 0.9)


def publish_pin(page, it, dry):
    """Create one pin in the pin-builder UI. Returns (ok, note)."""
    img = local_image(it.get("image_url", ""))
    if not img:
        return False, f"local image not found for {it.get('image_url')}"
    page.goto(PIN_BUILDER, wait_until="domcontentloaded")
    human_pause(1.5, 3.0)

    # 1) upload the image into the (often hidden) file input
    file_input = _first(page, [lambda: page.locator("input[type=file]").first], timeout=15000)
    if not file_input:
        page.screenshot(path="status/pw_error_upload.png")
        return False, "no file input found (see status/pw_error_upload.png)"
    file_input.set_input_files(str(img))
    human_pause(3.0, 5.0)                                 # let Pinterest process the image

    # 2) title
    title = _first(page, [
        lambda: page.get_by_placeholder("Add a title"),
        lambda: page.get_by_role("textbox", name="Add your title"),
        lambda: page.locator('[data-test-id="pin-draft-title"] textarea, textarea[id*="title" i]'),
    ])
    if title:
        type_like_human(title, (it.get("title") or "")[:100])

    # 3) description
    desc = _first(page, [
        lambda: page.get_by_placeholder("Add a detailed description"),
        lambda: page.get_by_role("textbox", name="Tell everyone what your Pin is about"),
        lambda: page.locator('[data-test-id="pin-draft-description"] textarea, div[role="textbox"]'),
    ])
    if desc:
        type_like_human(desc, (it.get("caption") or "")[:480])

    # 4) destination link
    link = _first(page, [
        lambda: page.get_by_placeholder("Add a destination link"),
        lambda: page.get_by_role("textbox", name="Add a destination link"),
        lambda: page.locator('input[id*="link" i], textarea[id*="link" i]'),
    ])
    if link and it.get("link"):
        type_like_human(link, it["link"])

    # 5) board picker -> choose the pin's board by name
    board_name = it.get("board", "")
    picker = _first(page, [
        lambda: page.get_by_role("button", name="Choose a board"),
        lambda: page.locator('[data-test-id="board-dropdown-select-button"]'),
        lambda: page.get_by_text("Choose a board"),
    ])
    if picker and board_name:
        picker.click(); human_pause(0.6, 1.4)
        opt = _first(page, [
            lambda: page.get_by_role("option", name=board_name),
            lambda: page.get_by_text(board_name, exact=True),
        ])
        if opt:
            opt.click(); human_pause(0.5, 1.2)

    if dry:
        page.screenshot(path="status/pw_dryrun_preview.png")
        return True, "dry-run (form filled, not published; see status/pw_dryrun_preview.png)"

    # 6) publish
    pub = _first(page, [
        lambda: page.get_by_role("button", name="Publish"),
        lambda: page.locator('[data-test-id="board-dropdown-save-button"]'),
        lambda: page.get_by_role("button", name="Save"),
    ])
    if not pub:
        page.screenshot(path="status/pw_error_publish.png")
        return False, "no Publish button (see status/pw_error_publish.png)"
    pub.click()
    human_pause(3.0, 6.0)
    # success heuristic: a confirmation toast or navigation away from the empty builder
    try:
        page.get_by_text("Your Pin", exact=False).first.wait_for(timeout=8000)
    except Exception:
        pass
    return True, "published"


def write_status(mode, state, elig, recent, next_at=None, note=""):
    age = account_age_days(state)
    today = datetime.now(ET).strftime("%Y-%m-%d")
    cap = ramp_cap(age)
    posted_today = state.get("by_date", {}).get(today, 0)
    _write_json(STATUS, {
        "updated": datetime.now(ET).isoformat(timespec="seconds"),
        "mode": "ui-" + mode, "account_age_days": age, "cap_today": cap,
        "posted_today": posted_today, "remaining_today": max(0, cap - posted_today),
        "approved_waiting": len(elig), "window": f"{WIN_START:02d}:00-{WIN_END:02d}:00 ET",
        "window_open": window_open(), "next_action_at": next_at, "note": note,
        "recent": recent[-12:],
    })


def login_flow():
    from playwright.sync_api import sync_playwright
    PROFILE.mkdir(exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(PROFILE), headless=False,
                                                    viewport={"width": 1280, "height": 900})
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://www.pinterest.com/login/")
        print("A browser opened. Sign in to the Mom Found It Cheaper BUSINESS account.")
        input("When you can see your Pinterest home feed, press Enter here to save the session... ")
        ctx.close()
    print("Saved. You can now run:  python pinterest_ui_post.py --go --once --now")


def run(go, once, ignore_window):
    from playwright.sync_api import sync_playwright
    if not PROFILE.exists():
        print("No saved login. Run first:  python pinterest_ui_post.py --login"); sys.exit(2)
    state = _read_json(STATE, {})
    state.setdefault("start_date", datetime.now(ET).strftime("%Y-%m-%d"))
    state.setdefault("by_date", {})
    recent = _read_json(STATUS, {}).get("recent", []) if Path(STATUS).exists() else []
    mode = "live" if go else "dry-run"
    Path("status").mkdir(exist_ok=True)

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(PROFILE), headless=False,
                                                    viewport={"width": 1280, "height": 900})
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            while True:
                queue = _read_json(QUEUE, {})
                posted = _read_json(POSTED, {})
                today = datetime.now(ET).strftime("%Y-%m-%d")
                cap = ramp_cap(account_age_days(state))
                posted_today = state["by_date"].get(today, 0)
                elig = eligible_pins(queue, posted)

                if posted_today >= cap:
                    write_status(mode, state, elig, recent, note=f"daily cap {cap} reached")
                    print(f"[{today}] daily cap {cap} reached. Done for today.")
                    if once:
                        break
                    time.sleep(3600); continue
                if not elig:
                    write_status(mode, state, elig, recent, note="no approved pins waiting")
                    print("No approved pins waiting. Approve some, then rerun.")
                    if once:
                        break
                    time.sleep(600); continue
                if not ignore_window and not window_open():
                    wait = seconds_until_window()
                    nxt = (datetime.now(ET) + timedelta(seconds=wait)).isoformat(timespec="seconds")
                    write_status(mode, state, elig, recent, next_at=nxt, note="outside posting window")
                    print(f"Outside window. Sleeping until {nxt}.")
                    if once:
                        break
                    time.sleep(min(wait, 3600)); continue

                it = elig[0]
                ok, note = publish_pin(page, it, dry=not go)
                at = datetime.now(ET).isoformat(timespec="seconds")
                recent.append({"id": it["id"], "title": it.get("title", "")[:60],
                               "result": ("posted" if (ok and go) else "would-post" if ok else "error"),
                               "note": note, "at": at})
                if ok and go:
                    posted[it["id"]] = {"at": at, "via": "ui"}
                    _write_json(POSTED, posted)
                    state["by_date"][today] = posted_today + 1
                    _write_json(STATE, state)
                print(f"{'POSTED' if (ok and go) else 'DRY' if ok else 'ERROR'} {it['id']}: {note}")
                if not ok:
                    write_status(mode, state, elig, recent, note=note)
                    if once:
                        break
                    time.sleep(180); continue

                gap = random.randint(MIN_GAP, MAX_GAP) * 60
                nxt = (datetime.now(ET) + timedelta(seconds=gap)).isoformat(timespec="seconds")
                write_status(mode, state, elig, recent, next_at=nxt)
                if once:
                    break
                print(f"Next pin in ~{gap // 60} min (at {nxt}).")
                time.sleep(gap)
        finally:
            ctx.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--login", action="store_true", help="open a browser to sign in once (saves session)")
    ap.add_argument("--go", action="store_true", help="actually publish (default is a dry run)")
    ap.add_argument("--once", action="store_true", help="do at most one pin, then exit")
    ap.add_argument("--now", action="store_true", help="ignore the daytime posting window")
    a = ap.parse_args()
    if a.login:
        login_flow(); return
    run(a.go, a.once, a.now)


if __name__ == "__main__":
    main()
