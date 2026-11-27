#!/usr/bin/env python3
"""Growth step: pull the day's metrics, rank the rule-safe plays with free models (OmniRoute), and
write control/growth.json for the dashboard. No Claude tokens.

Metrics come from each platform's own analytics when the API tokens are set (see launch/
N8N_PUBLISHING.md for Graph API + Pinterest; Amazon Associates report export). Until then the metric
values stay "—" and only the plays are produced. Every play is checked against the compliance guard in
launch/GROWTH_PLAYBOOK.md; only ok/required plays are emitted."""
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# Candidate plays, each pre-tagged against the compliance guard. Edit here; the tracker only emits
# rule ok/required and can re-order by what the metrics show is working.
PLAYS = [
    {"do": "Put the Amazon link in the FIRST COMMENT, not the post body",
     "why": "Facebook throttles posts with outbound links; comment links keep reach", "rule": "ok", "flag": "link_in_comment"},
    {"do": "Open every post with #ad and keep 'As an Amazon Associate I earn…'",
     "why": "FTC + Amazon Associates disclosure", "rule": "required", "flag": "disclosure"},
    {"do": "Short caption: emoji + the exact price + 'link in comments'",
     "why": "matches high-reach deal groups", "rule": "ok", "flag": "snappy_caption"},
    {"do": "Ask one genuine question (which color would you pick?)",
     "why": "real engagement lifts reach", "rule": "ok", "flag": "ask_question"},
    {"do": "Pinterest: fresh pin daily, keyword-rich title, paced 3–5/day on a new account",
     "why": "Pinterest rewards fresh pins; bursts look like spam", "rule": "ok", "flag": "paced_pins"},
    {"do": "Cross-post the Reel to FB + a Pinterest Idea pin",
     "why": "one asset, three surfaces", "rule": "ok", "flag": "crosspost"},
    {"do": "Invite friends + pin a friendly 'start here' post",
     "why": "seeds a new group organically", "rule": "ok", "flag": "seed"},
]
AVOID = [
    "Fake scarcity / countdowns that aren't real",
    "Fake or incentivised reviews, bought followers/likes",
    "Engagement-bait ('tag 10 friends', 'comment YES')",
    "Undisclosed affiliate links",
    "Copying other groups' posts or images, or using their name",
    "Saying a price without the Amazon read-time; prices change",
]
METRIC_KEYS = [
    ("FB group members", "confirm group restored, then track daily"),
    ("Post reach (7d avg)", "from Page/Group insights"),
    ("Link clicks (7d)", "first-comment link clicks"),
    ("Pinterest outbound clicks", "from Pinterest analytics once pins are live"),
    ("Associate orders (today)", "goal: first 3 → 10"),
    ("Associate earnings (MTD)", "from Amazon Associates"),
]


def metrics():
    """Fill from platform APIs when tokens exist (env). Placeholder '—' until wired."""
    vals = {}
    # e.g. vals["Associate orders (today)"] = amazon_report_today()   # when the export is wired
    return [{"k": k, "v": vals.get(k, "—"), "note": note} for k, note in METRIC_KEYS]


def main():
    plays = [p for p in PLAYS if p["rule"] in ("ok", "required")]   # compliance guard
    out = {
        "updated": datetime.now(ET).strftime("%Y-%m-%d"),
        "metrics": metrics(),
        "plays": [{"do": p["do"], "why": p["why"], "rule": p["rule"]} for p in plays],
        "active_flags": {p["flag"]: True for p in plays},    # make_posts/make_pins read these
        "avoid": AVOID,
    }
    d = Path("control")
    d.mkdir(exist_ok=True)
    (d / "growth.json").write_text(json.dumps(out, indent=2))
    print("growth.json:", len(out["plays"]), "plays,", len(out["metrics"]), "metrics")


if __name__ == "__main__":
    main()
