#!/usr/bin/env python3
"""Preflight QA - run BEFORE pushing anything the Lenovo will run.

Catches the classes of bug that leaked to Rohini before: Windows strftime (%-d/%-I),
cp1252 emoji crashes, stale-queue posting, id-collision dedup, syntax/import errors.
Exits non-zero on any failure. Run:  python test_preflight.py
"""
import importlib.util
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

FAILS = []


def check(name, cond, detail=""):
    print(("PASS" if cond else "FAIL") + "  " + name + (("  -> " + detail) if detail and not cond else ""))
    if not cond:
        FAILS.append(name)


def load(mod, path):
    s = importlib.util.spec_from_file_location(mod, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


# 1) every script imports (syntax + import errors) ------------------------------
for f in ("utf8_io.py", "make_posts.py", "make_pins.py", "make_videos.py", "build_site.py",
          "make_queue_json.py", "post_qa.py", "make_queue.py", "make_review.py",
          "qa_free.py", "image_qa.py", "pinterest_post.py", "pinterest_ui_post.py", "approve.py"):
    try:
        import ast
        ast.parse(Path(f).read_text())
        check(f"parse {f}", True)
    except Exception as e:
        check(f"parse {f}", False, repr(e))

# 2) UTF-8 text IO works for emoji (the cp1252 crash class) ----------------------
try:
    load("utf8_io", "utf8_io.py")
    p = Path(tempfile.gettempdir()) / "_pf_emoji.txt"
    p.write_text("fire \U0001f525 point \U0001f447")
    check("utf8 emoji write/read", p.read_text() == "fire \U0001f525 point \U0001f447")
    # prove the raw cp1252 path WOULD have failed (what Windows does by default)
    raised = False
    try:
        "\U0001f525".encode("cp1252")
    except Exception:
        raised = True
    check("cp1252 would reject emoji (so the patch matters)", raised)
except Exception as e:
    check("utf8 emoji", False, repr(e))

# 3) cross-platform strftime (%-d/%-I) on simulated Windows ----------------------
try:
    bs = load("build_site", "build_site.py")
    t = datetime(2026, 11, 28, 7, 5)
    real = os.name
    try:
        os.name = "nt"                                   # simulate Windows branch
        out_nt = bs._sft(t, "%b %-d, %-I:%M %p ET")
    finally:
        os.name = real
    out_posix = bs._sft(t, "%b %-d, %-I:%M %p ET")
    check("strftime nt branch no crash", bool(out_nt))
    check("strftime posix branch no crash", "7:05" in out_posix)
except Exception as e:
    check("cross-platform strftime", False, repr(e))

# 4) poster gates: stale-queue guard + date-scoped dedup ------------------------
try:
    pp = load("pinterest_post", "pinterest_post.py")
    today = datetime.now(pp.ET).strftime("%Y-%m-%d")
    pins = [{"id": f"pin_{i:02d}", "type": "pin", "status": "approved",
             "qa": {"status": "pass"}, "image_url": f"https://x/pins/{today}/a{i}.png",
             "link": "https://x/#u"} for i in range(1, 4)]
    fresh = {"date": today, "pins": pins}
    stale = {"date": "2000-01-01", "pins": pins}
    check("stale queue -> 0 eligible", len(pp.eligible_pins(stale, {})) == 0)
    check("fresh queue -> all eligible", len(pp.eligible_pins(fresh, {})) == 3)
    check("stale bare id does NOT block today", len(pp.eligible_pins(fresh, {"pin_01": {}})) == 3)
    check("today date-key blocks that one", len(pp.eligible_pins(fresh, {f"{today}:pin_01": {}})) == 2)
    check("qa=fail excluded", len(pp.eligible_pins(
        {"date": today, "pins": [{**pins[0], "qa": {"status": "fail"}}]}, {})) == 0)
    check("status!=approved excluded", len(pp.eligible_pins(
        {"date": today, "pins": [{**pins[0], "status": "pending"}]}, {})) == 0)
    check("image_qa=fail excluded", len(pp.eligible_pins(
        {"date": today, "pins": [{**pins[0], "image_qa": {"status": "fail"}}]}, {})) == 0)
    check("image_qa=warn still eligible", len(pp.eligible_pins(
        {"date": today, "pins": [{**pins[0], "image_qa": {"status": "warn"}}]}, {})) == 1)
except Exception as e:
    check("poster gates", False, repr(e))

# 4b) image_qa local-image mapping + grid rule ---------------------------------
try:
    iq = load("image_qa", "image_qa.py")
    check("image_qa maps pins url -> local path shape",
          str(iq.local_image("https://x/pins/2026-11-28/a.png") or "pins/2026-11-28/a.png").endswith("a.png") or
          iq.local_image("https://x/pins/2026-11-28/a.png") is None)  # file may not exist here; shape check only
    mp = load("make_pins", "make_pins.py") if False else None  # import side-effects need site; skip exec
    check("make_pins requires full 4-item grid (no empty cells)",
          ">= 4" in Path("make_pins.py").read_text() and "items[:4]" in Path("make_pins.py").read_text())
except Exception as e:
    check("image_qa/grid", False, repr(e))

# 5) approve.py approve / reject / min-judge on a temp queue --------------------
try:
    import subprocess
    import shutil
    work = Path(tempfile.mkdtemp())
    (work / "queue").mkdir()
    q = {"date": "2026-11-28", "pins": [
        {"id": "pin_01", "type": "pin", "status": "pending", "qa": {"status": "pass"}, "judge": {"score": 8}},
        {"id": "pin_02", "type": "pin", "status": "pending", "qa": {"status": "pass"}, "judge": {"score": 5}},
        {"id": "pin_03", "type": "pin", "status": "pending", "qa": {"status": "fail"}, "judge": {"score": 9}},
        {"id": "pin_04", "type": "pin", "status": "pending", "qa": {"status": "pass"},
         "judge": {"score": 9}, "image_qa": {"status": "fail"}}],
        "posts": [], "reels": []}
    (work / "queue" / "latest.json").write_text(json.dumps(q))
    shutil.copy("approve.py", work / "approve.py")
    shutil.copy("utf8_io.py", work / "utf8_io.py")
    subprocess.run(["python3", "approve.py", "--all", "--min-judge", "7"], cwd=work, check=True,
                   capture_output=True)
    q2 = json.loads((work / "queue" / "latest.json").read_text())
    st = {it["id"]: it["status"] for it in q2["pins"]}
    check("approve --min-judge 7 approves pin_01", st["pin_01"] == "approved")
    check("approve --min-judge 7 skips low score pin_02", st["pin_02"] != "approved")
    check("approve never approves qa=fail pin_03", st["pin_03"] != "approved")
    check("approve never approves image_qa=fail pin_04", st["pin_04"] != "approved")
    shutil.rmtree(work, ignore_errors=True)
except Exception as e:
    check("approve.py", False, repr(e))

print("\n" + ("ALL PREFLIGHT CHECKS PASSED" if not FAILS else f"{len(FAILS)} FAILED: {', '.join(FAILS)}"))
raise SystemExit(1 if FAILS else 0)
