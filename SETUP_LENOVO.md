# Run Amazon photos + ratings from your Lenovo (one-time setup, ~10 min)

Why: Amazon blocks cloud computers with a captcha, but not a normal home computer.
After setup it runs by itself every day: no Claude, no tokens.

1. Install Python 3 (python.org) and Git (git-scm.com) on the Lenovo.
2. Open Command Prompt:
   `git clone https://github.com/rohini0208/mom-found-it-cheaper-deals.git`
   (sign in to GitHub when asked)
3. Test: `cd mom-found-it-cheaper-deals` then `python amazon_local.py`
   It should print "ok B0..." lines and push photos.
4. Run daily: open Task Scheduler > Create Basic Task > Daily 6:00 AM >
   Action "Start a program": `python`, arguments `amazon_local.py`,
   Start in: the mom-found-it-cheaper-deals folder.
Keep the Lenovo on at that time. If it prints "captcha", it stops and tries again the next day.
