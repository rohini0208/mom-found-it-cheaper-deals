#!/usr/bin/env python3
"""Paced, human-like Pinterest drip poster (Pinterest API v5).

Posts ONLY pins Rohini has approved in the queue, one at a time, with randomized gaps,
a daily cap, a warm-up ramp for a new account, and a daytime posting window - so a fresh
account does not get flagged. Nothing posts unless you pass --go (default is a dry run).

Reads the token from a local .env (never committed):
    PINTEREST_TOKEN=pina_...              # access token (required to actually post)
    PINTEREST_BOARD_ID=123456789012345    # optional; else resolved from the pin's board name

Approval gate: a pin is eligible only when its queue item has status == "approved"
(set from the dashboard) and its QA status is not "fail". Everything else is skipped.

Usage:
    python pinterest_post.py                 # dry run: shows what it WOULD post, posts nothing
    python pinterest_post.py --go            # live: drips approved pins with pauses, loops
    python pinterest_post.py --go --once     # live: post at most one due pin, then exit (for a scheduler)
    python pinterest_post.py --go --now      # live: ignore the daytime window (still paced + capped)
"""
import utf8_io  # noqa: F401  (first import: forces UTF-8 text IO so Windows cp1252 can't crash on emoji)
import argparse
import base64
import json
import os
import random
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ET = timezone(timedelta(hours=-5))                       # US Eastern (winter); display/window only
API = "https://api.pinterest.com/v5"

QUEUE = Path("queue/latest.json")
POSTED = Path("data/pins_posted.json")                   # {pin_queue_id: {pin_id, at}}
STATE = Path("data/pinterest_state.json")                # {start_date, by_date:{YYYY-MM-DD: count}}
STATUS = Path("status/pinterest_status.json")            # dashboard feed

# Pacing knobs (env overrides). Defaults are deliberately gentle.
MIN_GAP = int(os.environ.get("PIN_MIN_GAP_MIN", "20"))   # minutes between posts (low)
MAX_GAP = int(os.environ.get("PIN_MAX_GAP_MIN", "45"))   # minutes between posts (high)
WIN_START = int(os.environ.get("PIN_WINDOW_START", "8"))  # earliest hour ET to post
WIN_END = int(os.environ.get("PIN_WINDOW_END", "21"))     # latest hour ET to post
TOKEN = os.environ.get("PINTEREST_TOKEN", "")
REFRESH = os.environ.get("PINTEREST_REFRESH", "")
BOARD_ID_ENV = os.environ.get("PINTEREST_BOARD_ID", "")
APP_ID = os.environ.get("PINTEREST_APP_ID", "1645680")
APP_SECRET = os.environ.get("PINTEREST_APP_SECRET", "")
REDIRECT = os.environ.get("PINTEREST_REDIRECT", "http://localhost:8085/")
SCOPES = os.environ.get("PINTEREST_SCOPES", "boards:read,pins:read,pins:write")


ENV_PATH = Path(".env")


def load_dotenv(path=".env"):
    """Minimal .env reader so the token/secret need not be exported each run."""
    global TOKEN, REFRESH, BOARD_ID_ENV, APP_SECRET, APP_ID
    p = Path(path)
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    TOKEN = os.environ.get("PINTEREST_TOKEN", TOKEN)
    REFRESH = os.environ.get("PINTEREST_REFRESH", REFRESH)
    BOARD_ID_ENV = os.environ.get("PINTEREST_BOARD_ID", BOARD_ID_ENV)
    APP_SECRET = os.environ.get("PINTEREST_APP_SECRET", APP_SECRET)
    APP_ID = os.environ.get("PINTEREST_APP_ID", APP_ID)


def update_env(updates):
    """Write/replace keys in .env, preserving other lines. Values are not quoted."""
    lines = ENV_PATH.read_text().splitlines() if ENV_PATH.exists() else []
    seen = set()
    out = []
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            k = s.split("=", 1)[0].strip()
            if k in updates:
                out.append(f"{k}={updates[k]}"); seen.add(k); continue
        out.append(line)
    for k, v in updates.items():
        if k not in seen:
            out.append(f"{k}={v}")
    ENV_PATH.write_text("\n".join(out) + "\n")


def _token_exchange(form):
    """POST /v5/oauth/token with HTTP Basic (app_id:app_secret). Returns the token JSON."""
    data = urllib.parse.urlencode(form).encode()
    basic = base64.b64encode(f"{APP_ID}:{APP_SECRET}".encode()).decode()
    req = urllib.request.Request(API + "/oauth/token", data=data, method="POST",
                                 headers={"Authorization": "Basic " + basic,
                                          "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def refresh_access_token():
    """Use the refresh token to mint a new access token; persist it to .env."""
    global TOKEN
    if not (REFRESH and APP_SECRET):
        return False
    try:
        tok = _token_exchange({"grant_type": "refresh_token", "refresh_token": REFRESH})
    except Exception:
        return False
    TOKEN = tok.get("access_token", TOKEN)
    update_env({"PINTEREST_TOKEN": TOKEN})
    return bool(tok.get("access_token"))


def diag():
    """Print the token's account, boards, and the full error from a test pin create."""
    load_dotenv()
    if not TOKEN:
        print("no PINTEREST_TOKEN in .env"); return
    def raw(method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(API + path, data=data, method=method,
                                     headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, r.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()
    s, b = raw("GET", "/user_account")
    print(f"user_account [{s}]: {b[:300]}")
    s, b = raw("GET", "/boards?page_size=50")
    print(f"boards [{s}]: {b[:600]}")
    try:
        boards = json.loads(b).get("items", [])
    except Exception:
        boards = []
    if boards:
        bid = boards[0]["id"]
        q = _read_json(QUEUE, {})
        pin = (q.get("pins") or [{}])[0]
        body = {"board_id": bid, "title": (pin.get("title") or "Test")[:100],
                "description": (pin.get("caption") or "test")[:800], "link": pin.get("link", ""),
                "media_source": {"source_type": "image_url", "url": pin.get("image_url", "")}}
        s, b = raw("POST", "/pins", body)
        print(f"create pin on board {bid} [{s}]: {b[:600]}")
    else:
        print("No boards returned for this token's account.")


def oauth_authorize():
    """One-time: run the OAuth code flow to get a pins:write token into .env."""
    global TOKEN, REFRESH
    if not APP_SECRET:
        print("ERROR: set PINTEREST_APP_SECRET in .env first (copy it from the app's Configure page)."); sys.exit(2)
    port = urllib.parse.urlparse(REDIRECT).port or 8085
    auth_url = ("https://www.pinterest.com/oauth/?" + urllib.parse.urlencode({
        "client_id": APP_ID, "redirect_uri": REDIRECT, "response_type": "code",
        "scope": SCOPES, "state": "mfic"}))
    holder = {}

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            holder["code"] = (q.get("code") or [""])[0]
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers()
            self.wfile.write(b"<h2>Authorized. You can close this tab and return to the terminal.</h2>")

        def log_message(self, *a):
            pass

    srv = HTTPServer(("localhost", port), H)
    threading.Thread(target=srv.handle_request, daemon=True).start()
    print("Opening Pinterest authorize page. If it does not open, paste this URL into Neo:\n" + auth_url)
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass
    print(f"Waiting for the redirect to {REDIRECT} ...")
    for _ in range(300):
        if holder.get("code"):
            break
        time.sleep(1)
    srv.server_close()
    code = holder.get("code")
    if not code:
        print("No authorization code received (timed out). Re-run --auth."); sys.exit(2)
    tok = _token_exchange({"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT})
    TOKEN = tok.get("access_token", ""); REFRESH = tok.get("refresh_token", "")
    if not TOKEN:
        print("Token exchange failed: " + json.dumps(tok)[:200]); sys.exit(2)
    update_env({"PINTEREST_TOKEN": TOKEN, "PINTEREST_REFRESH": REFRESH, "PINTEREST_APP_ID": APP_ID})
    granted = tok.get("scope", "(not reported)")
    print(f"Success. Wrote PINTEREST_TOKEN + PINTEREST_REFRESH to .env.")
    print(f"Requested scopes : {SCOPES}")
    print(f"GRANTED scopes   : {granted}")
    if "pins:write" not in str(granted):
        print("WARNING: pins:write was NOT granted. On the authorize screen you must allow Pin creation,")
        print("         and authorize on the Mom Found It Cheaper business account. Re-run --auth.")
    else:
        print("pins:write granted. Dry-run:  python pinterest_post.py   then live:  python pinterest_post.py --go")


def _read_json(p, default):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return default


def _write_json(p, obj):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, indent=2))


def ramp_cap(age_days):
    """Warm-up ramp for a new account: climb slowly over two weeks."""
    if age_days <= 2:
        return 3
    if age_days <= 6:
        return 5
    if age_days <= 13:
        return 8
    return 12


def account_age_days(state):
    start = state.get("start_date")
    if not start:
        return 0
    d0 = datetime.strptime(start, "%Y-%m-%d").date()
    return (datetime.now(ET).date() - d0).days


def window_open(now=None):
    now = now or datetime.now(ET)
    return WIN_START <= now.hour < WIN_END


def seconds_until_window(now=None):
    now = now or datetime.now(ET)
    if window_open(now):
        return 0
    nxt = now.replace(hour=WIN_START, minute=random.randint(0, 20), second=0, microsecond=0)
    if now.hour >= WIN_END:
        nxt = nxt + timedelta(days=1)
    return max(1, int((nxt - now).total_seconds()))


def api(method, path, body=None, _retry=True):
    url = API + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Authorization": "Bearer " + TOKEN,
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 401 and _retry and refresh_access_token():
            return api(method, path, body, _retry=False)   # token refreshed, retry once
        raise


def resolve_board_id(name, cache):
    if BOARD_ID_ENV:
        return BOARD_ID_ENV
    if name in cache:
        return cache[name]
    try:
        boards = api("GET", "/boards?page_size=100").get("items", [])
    except Exception:
        boards = []
    for b in boards:
        cache[b.get("name", "")] = b.get("id", "")
    return cache.get(name, "")


def eligible_pins(queue, posted):
    out = []
    for it in queue.get("pins", []):
        if it.get("status") != "approved":
            continue
        if (it.get("qa") or {}).get("status") == "fail":
            continue
        if it.get("id") in posted:
            continue
        if not it.get("image_url") or not it.get("link"):
            continue
        out.append(it)
    return out


def post_pin(it, board_cache):
    board_id = resolve_board_id(it.get("board", ""), board_cache)
    if not board_id:
        return None, "no board_id (set PINTEREST_BOARD_ID or check board name)"
    body = {
        "board_id": board_id,
        "title": (it.get("title") or "")[:100],
        "description": (it.get("caption") or "")[:800],
        "link": it.get("link", ""),
        "media_source": {"source_type": "image_url", "url": it["image_url"]},
    }
    try:
        res = api("POST", "/pins", body)
        return res.get("id", "posted"), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.read().decode()[:160]}"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def write_status(mode, state, elig, recent, next_at=None, note=""):
    age = account_age_days(state)
    today = datetime.now(ET).strftime("%Y-%m-%d")
    cap = ramp_cap(age)
    posted_today = state.get("by_date", {}).get(today, 0)
    _write_json(STATUS, {
        "updated": datetime.now(ET).isoformat(timespec="seconds"),
        "mode": mode,
        "account_age_days": age,
        "cap_today": cap,
        "posted_today": posted_today,
        "remaining_today": max(0, cap - posted_today),
        "approved_waiting": len(elig),
        "window": f"{WIN_START:02d}:00-{WIN_END:02d}:00 ET",
        "window_open": window_open(),
        "next_action_at": next_at,
        "note": note,
        "recent": recent[-12:],
    })


def run(go, once, ignore_window):
    load_dotenv()
    if go and not TOKEN:
        print("ERROR: --go needs PINTEREST_TOKEN (in .env or env). Aborting."); sys.exit(2)
    queue = _read_json(QUEUE, {})
    posted = _read_json(POSTED, {})
    state = _read_json(STATE, {})
    state.setdefault("start_date", datetime.now(ET).strftime("%Y-%m-%d"))
    state.setdefault("by_date", {})
    board_cache = {}
    recent = _read_json(STATUS, {}).get("recent", []) if STATUS.exists() else []
    mode = "live" if go else "dry-run"

    while True:
        queue = _read_json(QUEUE, {})                    # re-read so new approvals are picked up
        posted = _read_json(POSTED, {})
        today = datetime.now(ET).strftime("%Y-%m-%d")
        age = account_age_days(state)
        cap = ramp_cap(age)
        posted_today = state["by_date"].get(today, 0)
        elig = eligible_pins(queue, posted)

        if posted_today >= cap:
            write_status(mode, state, elig, recent, note=f"daily cap {cap} reached")
            print(f"[{today}] daily cap {cap} reached ({posted_today}). Done for today.")
            if once:
                return
            time.sleep(seconds_until_window(datetime.now(ET) + timedelta(days=1)) or 3600)
            continue

        if not elig:
            write_status(mode, state, elig, recent, note="no approved pins waiting")
            print("No approved pins waiting. Approve some in the dashboard.")
            if once:
                return
            time.sleep(600)
            continue

        if not ignore_window and not window_open():
            wait = seconds_until_window()
            nxt = (datetime.now(ET) + timedelta(seconds=wait)).isoformat(timespec="seconds")
            write_status(mode, state, elig, recent, next_at=nxt, note="outside posting window")
            print(f"Outside window ({WIN_START}:00-{WIN_END}:00 ET). Sleeping until {nxt}.")
            if once:
                return
            time.sleep(min(wait, 3600))
            continue

        it = elig[0]
        if go:
            pin_id, err = post_pin(it, board_cache)
        else:
            pin_id, err = "DRYRUN", None

        at = datetime.now(ET).isoformat(timespec="seconds")
        if err:
            recent.append({"id": it["id"], "title": it.get("title", "")[:60], "result": "error", "error": err, "at": at})
            write_status(mode, state, elig, recent, note=f"error on {it['id']}")
            print(f"ERROR posting {it['id']}: {err}")
            if once:
                return
            time.sleep(120)
            continue

        if go:
            posted[it["id"]] = {"pin_id": pin_id, "at": at}
            _write_json(POSTED, posted)
            state["by_date"][today] = posted_today + 1
            _write_json(STATE, state)
        recent.append({"id": it["id"], "title": it.get("title", "")[:60],
                       "result": ("posted" if go else "would-post"), "pin_id": pin_id, "at": at})
        print(f"{'POSTED' if go else 'WOULD POST'} {it['id']} -> pin {pin_id}  ({posted_today + (1 if go else 0)}/{cap} today)")

        gap = random.randint(MIN_GAP, MAX_GAP) * 60
        nxt = (datetime.now(ET) + timedelta(seconds=gap)).isoformat(timespec="seconds")
        write_status(mode, state, elig, recent, next_at=nxt)
        if once:
            return
        print(f"Next pin in ~{gap // 60} min (at {nxt}).")
        time.sleep(gap)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--auth", action="store_true", help="one-time OAuth: get a pins:write token into .env")
    ap.add_argument("--diag", action="store_true", help="print token account, boards, and full pin-create error")
    ap.add_argument("--go", action="store_true", help="actually post (default is a dry run)")
    ap.add_argument("--once", action="store_true", help="post at most one due pin, then exit")
    ap.add_argument("--now", action="store_true", help="ignore the daytime posting window")
    a = ap.parse_args()
    if a.auth:
        load_dotenv()
        oauth_authorize()
        return
    if a.diag:
        diag()
        return
    run(a.go, a.once, a.now)


if __name__ == "__main__":
    main()
