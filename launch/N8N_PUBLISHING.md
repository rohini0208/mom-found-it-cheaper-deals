# n8n auto-publishing — Pinterest + Facebook Page (spec)

Goal: publish the daily pins and posts that the GitHub pipeline already produces, with no file
uploads and no browser automation, by calling the Pinterest and Facebook APIs from n8n. Keep the
approval gate (nothing posts until Rohini approves) and pace posts so a fresh account is not flagged.

Why this works where the browser route failed: both APIs accept an **image URL** and a **destination
link** directly. The pins are already live at `https://momfounditcheaper.com/pins/<date>/...`, so n8n
just passes the URL — full-res image **and** the correct Associate link, no file picker.

Runs on the Lenovo in the existing n8n (C:\AI_Studio), same box as the scraper.

---

## 0. Data the workflow consumes

The pipeline will emit one machine-readable file per day that n8n reads (added to `make_pins.py` /
`make_posts.py` — see §5). Published to the site so n8n can HTTP GET it:

`https://momfounditcheaper.com/pins/<ET-date>/pins_api.json`

```json
{
  "date": "2026-11-27",
  "pins": [
    {
      "image_url": "https://momfounditcheaper.com/pins/2026-11-27/pin_under-10.png",
      "title": "Under $10 mom finds — verified on Amazon Nov 27",
      "description": "#ad Under $10 finds for moms ... As an Amazon Associate I earn from qualifying purchases.",
      "link": "https://momfounditcheaper.com/#under-10",
      "board": "Mom-Approved Finds"
    }
  ]
}
```

And for Facebook, `https://momfounditcheaper.com/posts/<ET-date>/posts_api.json`:

```json
{
  "date": "2026-11-27",
  "posts": [
    {
      "message": "#ad 🔥 Under $10 mom finds, checked on Amazon this morning. Link in comments 👇",
      "image_url": "https://momfounditcheaper.com/posts/2026-11-27/post_under-10.png",
      "comment": "#ad Shop here (prices change): https://momfounditcheaper.com/#under-10"
    }
  ],
  "reels": [
    { "video_url": "https://momfounditcheaper.com/videos/2026-11-27/deal_1.mp4",
      "description": "#ad ..." }
  ]
}
```

---

## 1. Pinterest token setup (one time)

1. Go to https://developers.pinterest.com → create an app (connect it to the business account
   `Mom Found It Cheaper`).
2. App settings:
   - Redirect URI: `https://localhost/callback` (or your n8n OAuth callback URL).
   - Scopes: `boards:read`, `boards:write`, `pins:read`, `pins:write`, `user_accounts:read`.
3. Note `App ID` (client_id) and `App secret` (client_secret).
4. Trial access is enough to post to your own boards (lower rate limits, ~1000 calls/day — fine for
   12–20 pins). Request "Standard access" later if you scale; it needs a short use-case review.
5. OAuth 2.0 to get tokens (do once):
   - In n8n, add a **Generic OAuth2** credential:
     - Auth URL: `https://www.pinterest.com/oauth/`
     - Token URL: `https://api.pinterest.com/v5/oauth/token`
     - Client ID / Secret: from step 3
     - Scope: the five scopes above, space-separated
     - Auth: send client credentials in the body (Pinterest uses Basic auth header; n8n handles it)
   - Connect → approve → n8n stores `access_token` (expires ~30 days) + `refresh_token` (~1 year).
     n8n refreshes the access token automatically with the generic OAuth2 credential.
6. Get the board id once (store it as an n8n variable / in pins_api.json):
   - `GET https://api.pinterest.com/v5/boards` → find `"name": "Mom-Approved Finds"` → copy its `id`.

## 2. Facebook Page token setup (one time)

1. https://developers.facebook.com → create an app, type "Business".
2. Add product **Facebook Login**. Keep the app in **Development** mode — as the Page admin/developer
   you can post to your **own** Page without full App Review.
3. Graph API Explorer → select your app → get a **User** token with scopes:
   `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`.
4. `GET /me/accounts` → find the Page `Mom Found It Cheaper - Daily Updates` → copy its
   `access_token` (a Page token) and its `id` (page-id).
5. Make the Page token long-lived / non-expiring:
   - Exchange the user token for a long-lived one:
     `GET /oauth/access_token?grant_type=fb_exchange_token&client_id=<app-id>&client_secret=<app-secret>&fb_exchange_token=<user-token>`
   - Then `GET /me/accounts` again with the long-lived user token → the returned Page token does not
     expire. Store it in an n8n credential.
6. API version: use the current Graph version, e.g. `https://graph.facebook.com/v21.0`.

Store both tokens in **n8n credentials**, never in the workflow JSON.

---

## 3. n8n workflow — Pinterest branch

Nodes, in order:

1. **Schedule Trigger** — daily, after the pipeline's 7:41 AM render (e.g. 9:00 AM ET). Or a
   **Webhook** the pipeline hits when the queue is ready.
2. **Approval gate** (pick one):
   - **GitHub Trigger** on the `approval` issue: fire only when Rohini comments `approve`.
   - or **Telegram** node: send the day's queue, wait for an "Approve" callback button.
   Nothing past this node runs until approved.
3. **HTTP Request — get queue**: `GET https://momfounditcheaper.com/pins/<date>/pins_api.json`.
4. **Split In Batches** (batch size 1) over `pins[]` — this is the pacing loop.
5. **HTTP Request — create pin**:
   - Method: `POST`
   - URL: `https://api.pinterest.com/v5/pins`
   - Auth: the Pinterest OAuth2 credential
   - Headers: `Content-Type: application/json`
   - Body (JSON):
     ```json
     {
       "board_id": "{{ $env.PIN_BOARD_ID }}",
       "title": "{{ $json.title }}",
       "description": "{{ $json.description }}",
       "link": "{{ $json.link }}",
       "media_source": {
         "source_type": "image_url",
         "url": "{{ $json.image_url }}"
       }
     }
     ```
   - A 201 response returns the new pin `id`.
6. **Wait** node — 20–40 min between pins (pacing). For a fresh account cap at ~3–5 pins/day; let the
   rest roll to the next run.
7. (optional) **Set / log** node — append the pin id + timestamp to a log (so re-runs skip done pins).

## 4. n8n workflow — Facebook Page branch

Same trigger + approval gate. Then:

- **Text + link post** (highest reach pattern, link in first comment):
  1. **HTTP Request — create post**:
     `POST https://graph.facebook.com/v21.0/{page-id}/feed`
     body: `message={{ $json.message }}`, `access_token=<page token>` (from credential).
     Returns the post `id` (format `pageid_postid`).
  2. **HTTP Request — first comment with the link**:
     `POST https://graph.facebook.com/v21.0/{post-id}/comments`
     body: `message={{ $json.comment }}` (the Amazon/site link lives here, not in the post — this is
     how Smart Savers gets reach).
- **Photo post** (when you want the image in-feed):
  `POST https://graph.facebook.com/v21.0/{page-id}/photos`
  body: `url={{ $json.image_url }}`, `caption={{ $json.message }}`, `access_token=...`
  (Graph fetches the image from the URL — no upload.)
- **Reel** (video):
  three calls to `POST /v21.0/{page-id}/video_reels`:
  1. `upload_phase=start` → returns `video_id` + `upload_url`.
  2. upload: either transfer the bytes, or use the hosted-file path — `POST` the `upload_url` with
     header `file_url: {{ $json.video_url }}` (the release/site MP4 URL).
  3. `upload_phase=finish&video_id=<id>&video_state=PUBLISHED&description=<caption>`.
  Pace reels heavily (1–2/day max on a fresh page).

Between posts, a **Wait** node for pacing, same as Pinterest.

---

## 5. Pipeline changes to feed n8n (small)

- `make_pins.py`: also write `pins/<date>/pins_api.json` (the schema in §0) next to `pins.csv`. The
  fields already exist in the CSV rows — just emit JSON too.
- `make_posts.py`: write `posts/<date>/posts_api.json` with `message`, `image_url`, `comment` per
  post (and move the link into `comment`, per the Smart Savers pattern we studied).
- `make_videos.py` / release: expose each MP4 at a public URL (either copy to the site under
  `videos/<date>/` so Cloudflare serves it, or use the GitHub release asset URL) for the Reels
  `file_url`.
- `build_site.py`: make sure `pins/`, `posts/`, `videos/` JSON + media are deployed (they mostly are;
  add the JSON files to the build copy list).

I can make these pipeline edits when you want — they're additive and don't change what's rendered.

---

## 6. Keep the rules

- **Approval gate**: the publish nodes sit *after* the approval node. No approval → nothing posts.
- **Pacing**: Wait nodes + a per-day cap (Pinterest ~3–5, FB ~2–3 posts, ~1 reel) while the accounts
  are new — important given the Nov 16 group suspension.
- **Accuracy**: n8n posts exactly what the pipeline QA'd (same images, prices, links). No new content
  is generated at publish time.
- **Secrets**: tokens live in n8n credentials. Rotate if the Lenovo is shared.

## 7. Token maintenance

- Pinterest access token expires ~30 days; the OAuth2 credential auto-refreshes with the refresh
  token (valid ~1 year — re-auth yearly).
- Facebook long-lived Page token (from §2.5) does not expire, but revoke/rotate if exposed. If you
  used a 60-day user token instead, refresh it every ~50 days.

## 8. Test before going live

1. Point the Pinterest create-pin node at ONE pin, run manually → confirm it appears on the
   "Mom-Approved Finds" board with the right link.
2. Post ONE Facebook text+link + comment to the Page → confirm the comment carries the link.
3. Then enable the approval gate + pacing and let it run the full queue.
