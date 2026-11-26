# Mom Found It Cheaper — autopilot revenue plan (v1, 2026-11-25)

Goal: a second income stream from Amazon Associates that runs on its own, with Rohini approving
a daily queue. Not a job replacement. First milestone: 3 sales (keeps the account), then 10 sales
in a rolling 30 days (unlocks Creators API for official photos/prices).

## Brand
- Persona: **Mia** (AI character, Google Flow Character "Mia (Mom Found It Cheaper) v1"), the Tampa mom
  behind the brand. Rohini stays private. Mia "finds" deals; she never claims to own or test a product.
- Assets: brand/mia_avatar_800.jpg (profile), brand/fb_cover_1640x624.jpg, brand/yt_banner_2560x1440.jpg,
  site header uses brand/mia_avatar_circle_240.png.
- Look: pastel peach/mint, Playfair + Inter, cute and clean. No red/black backgrounds (Rohini's rule).

## Channels (in order of expected payoff)
1. **Facebook Page** (engine). Turn on *Facebook Affiliate Partnerships* (FB app → Professional
   Dashboard → Monetization): tag Amazon products in Reels/photo posts, Meta shows name+price+Prime,
   7-day attribution. Until then: post site links (momfounditcheaper.com), never raw amazon.com links.
   5–10 deal posts/day + 1 engagement post/day (poll / "deal or dud" / "what should I find cheaper?").
2. **Website** momfounditcheaper.com (hub). Verified cards, Mia header, email signup (todo), Top-15 block (todo).
3. **New YouTube channel** (Mia, faceless). Daily Short: Mia card + product photo + voiceover.
   Create the channel (brand account, not personal); upload banner from brand/. Shorts link to the site.
4. **Pinterest** (compounding, free). One pin per verified deal → site. First clicks in 30–90 days.
5. **Group** (community layer) only after Facebook confirms it is restored. Rules pinned; Mia welcome post.

## Daily autopilot (GitHub Actions, no tokens)
- deals.yml every 3h: find deals, fetch photos, trends.
- Lenovo 6:00 AM: amazon_local.py — ASINs (450/run), titles, availability, link check.
- videos.yml 7:41 AM ET: videos, posts, strict post QA, **make_queue.py** → GitHub issue
  "Approval queue YYYY-MM-DD" (label `approval`). Rohini replies "post 1, q2; video 3; eng poll".
- Posting: manual for now (copy from the issue). Next build: Page poster via Graph API that posts
  only the items approved in the issue comment.

## Approval cadence
- Daily, 5 minutes: open the approval issue, reply with what to post.
- Weekly, 10 minutes: read status.py output + Associates Central clicks/orders; adjust categories.

## Compliance (do not break)
- AMAZON_PRICES=hide: no scraped Amazon prices or ratings on site/posts. Photos on (owner decision).
- Disclosure on every post and near every link. No self/family purchases, no incentives, no paid ads to Amazon.
- Every card/post passes verify_link (right product, buyable) before it can be queued.

## Engagement ideas (rotate)
- "Comment what you want found cheaper" (Mia replies with a verified find next day).
- Weekly poll: category / budget / store.
- "Deal or dud" on one item/day.
- Age-based gift lists on request ("kid is 6 → 3 finds under $20").
- Seasonal lists already in seasonal.py (stocking stuffers, baking, football).

## Metrics (weekly)
- Clicks/day (Associates Central) — target 50+ by week 3.
- Ordered items — target 3 by Dec 15, 10/30 days by late January.
- Page followers, email signups, Pinterest outbound clicks.
- If clicks high and orders zero: change picks (under $25, true discounts). If clicks low: traffic problem.

## Backlog (next builds)
- Email signup on site (Buttondown/Mailchimp free tier) and daily "top 5" send.
- Top-15 block with SiteStripe Text+Image embeds (needs Rohini signed into Amazon in Neo).
- Pinterest pin generator + scheduler (free API or manual batch).
- Page poster via Graph API, gated by the approval issue.
- YouTube Shorts with Mia + ElevenLabs/edge-tts voice, auto-upload gated by approval.
- Fix Lenovo scraper: ratings drift, list-price selector, seller blank.
