"""Records a deal as "Tested today" when the repo owner opens an issue
titled "tested: <deal id>" (the "Mark tested today" link on the site does this).
"""

import json
import os
import re
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

title = os.environ.get("ISSUE_TITLE", "")
if not title.lower().startswith("tested:"):
    sys.exit("not a tested issue")
deal = title.split(":", 1)[1].strip()
f = Path("data/tested.json")
tested = json.loads(f.read_text()) if f.exists() else {}
# Shown as "Tested Nov 12" on the site. If the issue text contains the
# Amazon product link (pasted from the product page), its product ID is
# saved too, so the deal button uses YOUR affiliate link.
body = urllib.parse.unquote(os.environ.get("ISSUE_BODY", ""))
asin = re.search(r"(?:/dp/|/gp/product/|/gp/aw/d/)([A-Z0-9]{10})", body)
tested[deal] = {"date": datetime.now(timezone.utc).strftime("%b %d"), "asin": asin.group(1) if asin else ""}
f.write_text(json.dumps(tested, indent=1))
print("marked tested:", deal)
