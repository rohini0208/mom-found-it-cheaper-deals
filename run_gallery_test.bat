@echo off
cd /d C:\Users\rajan\mom-found-it-cheaper-deals
git stash >nul 2>&1
git pull --rebase
python amazon_local.py B0D9WW3YND B0CGY3VF3K B0G5WWT1L1 B09C1Y9DRL B0D9R9WBQT B0G769Z84B B0DK8MPRGG B0DSQYHXZW >> gallery_test_log.txt 2>&1
