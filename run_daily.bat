@echo off
cd /d C:\Users\rajan\mom-found-it-cheaper-deals
git stash >nul 2>&1
git pull --rebase
python amazon_local.py >> daily_log.txt 2>&1
