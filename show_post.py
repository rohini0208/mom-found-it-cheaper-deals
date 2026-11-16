"""Print the exact caption and first comment to paste. Never type links from memory: copy from here."""
import sys
t = open(f"posts/{sys.argv[1]}.txt").read()
cap, cm = t.split("FIRST COMMENT")
print("=== CAPTION ===\n" + cap.replace("CAPTION:", "").strip())
print("\n=== FIRST COMMENT ===\n" + cm.split("\n", 1)[1].strip())
