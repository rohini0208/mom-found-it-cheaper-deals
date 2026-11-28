@echo off
REM Morning prep for Mom Found It Cheaper deal posting - RENDER + QA ONLY, never posts.
REM Schedule this to run early (see README note). When you wake, you just approve + drip:
REM     python approve.py --all --min-judge 7
REM     python pinterest_ui_post.py --go
REM
REM Loads secrets from .env (gitignored): OMNIROUTE_URL, OMNIROUTE_KEY (for qa_free),
REM plus the PINTEREST_* values. The .env must contain:
REM     OMNIROUTE_URL=http://localhost:20128/v1
REM     OMNIROUTE_KEY=sk-...        (your OmniRoute gateway key)

cd /d C:\Users\rajan\mom-found-it-cheaper-deals
set PYTHONUTF8=1

echo [prep] pulling latest...
git pull

echo [prep] loading .env...
for /f "usebackq tokens=1,* delims==" %%a in (".env") do set "%%a=%%b"

echo [prep] rendering posts, site, pins, queue...
python make_posts.py
python build_site.py
python make_pins.py
python make_queue_json.py
python growth_tracker.py

echo [prep] running free-AI QA + judge (caption text)...
python qa_free.py queue\latest.json

echo [prep] running vision QA (checks the actual images)...
python image_qa.py queue\latest.json

echo [prep] saving render + scores...
git add -A
git commit -m "daily prep: render + QA (%date%)"
git pull --rebase -X theirs
git push

echo [prep] DONE. Nothing posted. Now approve + drip when you are ready:
echo     python approve.py --all --min-judge 7
echo     python pinterest_ui_post.py --go
