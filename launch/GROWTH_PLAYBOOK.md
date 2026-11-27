# Growth playbook — grow the group + drive Amazon Associate sales, within every rule

Goal: more members and the first 3 → 10 Amazon Associate sales, with zero rule violations. This file
is the source of truth for the dashboard's **Growth** step and for `growth_tracker.py`. Every play is
checked against the compliance guard below before it reaches the posting workflow.

## The compliance guard (hard rules — a play that breaks any of these is dropped)

- **FTC**: every deal post opens with `#ad` and carries `As an Amazon Associate I earn from qualifying
  purchases.` No undisclosed affiliate links, ever.
- **Amazon Associates Operating Agreement**:
  - No price/▲rating/"was" claim unless it carries the time it was read ("Amazon price 7:12 AM ET"),
    because prices change. No "lowest ever / cheapest" unless it is literally true from our own log.
  - No Amazon data pulled by scraping presented as live; show the read time and "prices change".
  - Associate links only where allowed (not in email/PDF/off-platform in ways the agreement forbids).
  - Don't call the program/Amazon in a way that implies endorsement by Amazon.
- **Facebook**: no engagement-bait ("tag 10 friends", "comment YES"), no fake accounts, no buying
  likes/members, no reposting other groups' posts/images or using their name. Genuine questions are fine.
- **Pinterest**: fresh pins (not the same image spammed), paced (3–5/day on a new account), no misleading
  claims, no cloaked links. Link must go to a real page about the pinned item.
- **No fake scarcity, fake reviews, fake testimonials, or invented people.**
- **Child safety / prohibited goods**: no knives/weapons, no kids-targeted unsafe items (already
  filtered by the blocklist + `_NO_SITE`).

`growth_tracker.py` passes each candidate play through this list; only `rule: ok|required` plays are
shown in the dashboard and fed to the workflow.

## Plays that work (and are allowed)

Reach:
- **Link in the first comment, not the post body** — Facebook throttles outbound-link posts; the
  comment link keeps reach. (This is the single biggest lever; from the Smart Savers study.)
- **Short, specific caption**: emoji + the exact price + "link in comments 👇", `#ad` first.
- **One genuine question** per post ("which color would you pick?") — real engagement, not bait.
- **Cross-post**: the same Reel to FB, a Pinterest Idea pin, and (later) IG Reels — one asset, three
  surfaces.
- **Pin a friendly "start here" post** and keep a light weekly "best deal of the week" roundup.

Growth:
- **Invite friends** manually (allowed), seed the group before scaling.
- **Fresh daily pins** with keyword-rich titles (Pinterest is a search engine) — paced.
- **Consistent cadence** beats volume: a few strong posts/day > a dump.

Sales:
- Lead with benefit + price, not just "deal". Benefit-led captions convert (from the Reel benchmark).
- Real in-use photo as the first thing seen (pins/reels already do this).
- Round up by use-case ("gifts under $10", "kitchen finds") so one click browses many.

## Metrics the tracker watches (fed into the dashboard)

- Facebook: group members, post reach (7d avg), link clicks (first-comment).
- Pinterest: impressions, saves, outbound clicks.
- Amazon Associates: clicks, orders (today), earnings (MTD). **Goal: first 3 → 10 orders.**
- Each metric sourced from the platform's own analytics (Graph API / Pinterest analytics / Associates
  report) by `growth_tracker.py`; no guesses.

## How it feeds back (closed loop, no tokens)

1. `growth_tracker.py` pulls yesterday's metrics, asks OmniRoute free models which plays correlated
   with reach/clicks/sales, filters candidates through the compliance guard, writes `control/growth.json`.
2. The dashboard Growth view shows metrics + today's rule-safe plays + the "never do" list.
3. The posting workflow (make_posts / make_pins / make_videos) reads the active plays flags (e.g.
   `link_in_comment: true`, `ask_question: true`) so the day's content already follows what's working.
4. Nothing posts without approval; plays only change *how* the queued content is shaped, never bypass
   the approval gate.
