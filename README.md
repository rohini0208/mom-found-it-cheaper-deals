# Mom Found It Cheaper - deal finder and website

Every 3 hours, GitHub runs `deal_finder.py` for free. It reads the public
Slickdeals and DealNews RSS feeds, keeps only Amazon deals, and updates:

- **[DEALS.md](DEALS.md)** - the deal list (open it in the GitHub app on your phone)
- `deals.html` - the same list as a web page

No Claude and no API keys are used when it runs.

**Run it now:** Actions tab -> "Update deal list" -> Run workflow.

**Before posting a deal:** open it, check the price is real, make your own
SiteStripe link, and add #ad. Never repost the Slickdeals/DealNews link.

**Change sources or timing:** edit `FEEDS` in `deal_finder.py`, or the
`cron` line in `.github/workflows/deals.yml`.

## Daily videos (free, faceless)

Every morning `make_videos.py` turns the 3 best new deals into 14-second vertical Reels
(hook, product, price + code, "link in our Facebook group") with an AI voice.
Download them from **Releases -> Today's videos** (each video has a `.txt` caption).
No product photos are used, to follow Amazon's rules.

## Viral products

`viral_finder.py` lists the fastest-growing "Amazon finds" Shorts on YouTube in **VIRAL.md**.
It needs a free YouTube API key saved as the repo secret `YT_API_KEY`.

## The website (one place for everything)

Every 3 hours the site is rebuilt and published at
https://mom-found-it-cheaper-deals.pages.dev/ (Cloudflare Pages, rebuilt on every push) with viral finds, deals,
codes (tap to copy), coupons, our own price history and community votes.

- **Mark a code as tested:** open the site once with `?admin=1` on the end of the
  address (your phone remembers it), then tap "Mark tested today" on a deal. It opens
  a GitHub issue; send it, and within a minute the deal shows a green "Tested" badge.
- **Your Amazon links:** when you have your Associates ID, add it in
  Settings -> Secrets and variables -> Actions -> **Variables** -> `AMAZON_TAG`.
