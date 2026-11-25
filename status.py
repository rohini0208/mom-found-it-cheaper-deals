"""Did the 6 AM Lenovo run and the 3-hourly deal finder work? Run: python status.py  (after git pull)"""
import json, subprocess, time
from pathlib import Path

def last(author):
    r = subprocess.run(["git", "log", "-1", f"--author={author}", "--format=%ad|%s", "--date=format:%a %b %d %H:%M"],
                       capture_output=True, text=True).stdout.strip()
    return r or "none"

m = json.loads(Path("data/product_meta.json").read_text())
chk = [v["checked"] for v in m.values() if v.get("checked")]
age = (time.time() - max(chk)) / 3600 if chk else 999
fresh = sum(1 for c in chk if time.time() - c < 26 * 3600)
print("Lenovo (photo-bot) last push :", last("photo-bot"))
print("Deal finder (deal-bot) last  :", last("deal-bot"))
print(f"Amazon data newest check     : {age:.1f} h ago, {fresh} products fresh (<26h)")
rep = Path("data/link_report.json")
if rep.exists():
    r = json.loads(rep.read_text())
    ok = sum(1 for x in r.values() if x["ok"])
    print(f"Link check                   : {ok} ok, {len(r) - ok} rejected")
print("VERDICT:", "6 AM run OK" if age < 26 and fresh > 100 else "6 AM run MISSING/STALE - check Task Scheduler + daily_log.txt")
