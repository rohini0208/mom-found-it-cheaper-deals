"""Mom Found It Cheaper - viral product finder.

Uses the free YouTube Data API to list the most-watched "Amazon finds"
style Shorts from the last 7 days. The products in them are the viral
picks for the group. Writes VIRAL.md.

Needs a free API key in the environment variable YT_API_KEY
(stored as a GitHub secret). Without it, this script just skips.
Each run uses about 600 of the 10,000 free daily quota units.
"""

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEARCHES = [
    "amazon finds",
    "amazon must haves",
    "tiktok made me buy it",
    "amazon home finds",
    "amazon kitchen gadgets",
    "mom amazon finds",
]
DAYS = 7
PER_SEARCH = 15
API = "https://www.googleapis.com/youtube/v3/"


def get(endpoint, **params):
    params["key"] = os.environ["YT_API_KEY"]
    url = API + endpoint + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def main():
    if not os.environ.get("YT_API_KEY"):
        print("YT_API_KEY not set - skipping viral finder")
        return
    since = (datetime.now(timezone.utc) - timedelta(days=DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ids, found_by = [], {}
    for q in SEARCHES:
        res = get("search", part="id", q=q, type="video", videoDuration="short",
                  order="viewCount", publishedAfter=since, regionCode="US",
                  relevanceLanguage="en", maxResults=PER_SEARCH)
        for item in res.get("items", []):
            vid = item["id"]["videoId"]
            if vid not in found_by:
                ids.append(vid)
                found_by[vid] = q
    videos = []
    for i in range(0, len(ids), 50):
        res = get("videos", part="snippet,statistics", id=",".join(ids[i:i + 50]))
        for v in res.get("items", []):
            views = int(v["statistics"].get("viewCount", 0))
            published = datetime.fromisoformat(v["snippet"]["publishedAt"].replace("Z", "+00:00"))
            hours = max((datetime.now(timezone.utc) - published).total_seconds() / 3600, 1)
            videos.append({
                "title": v["snippet"]["title"].replace("|", "/"),
                "channel": v["snippet"]["channelTitle"].replace("|", "/"),
                "views": views,
                "per_hour": int(views / hours),
                "url": f"https://www.youtube.com/shorts/{v['id']}",
                "search": found_by[v["id"]],
            })
    videos.sort(key=lambda v: v["per_hour"], reverse=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Viral product ideas",
        "",
        f"Updated {now}. Most-watched product Shorts from the last {DAYS} days, fastest-growing first.",
        "Watch the top ones, note the product, then find it on Amazon and make your own SiteStripe link.",
        "",
        "| Views/hour | Views | Short | Channel | Found by |",
        "|---|---|---|---|---|",
    ]
    for v in videos[:60]:
        lines.append(f"| {v['per_hour']:,} | {v['views']:,} | [{v['title']}]({v['url']}) | {v['channel']} | {v['search']} |")
    Path("VIRAL.md").write_text("\n".join(lines) + "\n")
    print(f"{len(videos)} viral Shorts listed")


if __name__ == "__main__":
    main()
