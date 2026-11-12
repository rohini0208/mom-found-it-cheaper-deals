# Mom Found It Cheaper - deal finder

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
