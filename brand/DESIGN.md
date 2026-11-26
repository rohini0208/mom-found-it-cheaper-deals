# Mom Found It Cheaper — design system (why it looks the way it does)

Tokens live in `brand.py`. This file is the evidence behind them. Re-read before changing any visual.

## What the data says
- **Faces.** Breakout YouTube thumbnails use a face 69% of the time, rising to 80% in the top 50
  (vidIQ, 500 breakouts, June 2026). Eden's 507k-video study: faces are the norm (84% both groups);
  eye contact and a calm/genuine expression lean positive; exaggerated/shocked faces do not help small
  channels. → Mia on every cover/thumbnail, eye contact, warm smile, never a shocked face.
- **Text.** 72–87% of winners carry overlay text; the 4–6 word band is the biggest edge; 7+ words loses;
  all caps is slightly more common on winners. → Headline max 5 words, price in large type.
- **Contrast beats color.** Pixel-level saturation/brightness show no difference; "high contrast" is
  present in ~half of breakouts; the famous "red button +21%" test was an isolation effect (the only
  thing that stood out), not red itself. → Soft pastel base, ONE saturated accent (coral) reserved for
  price/CTA/hook word. Nothing else may be saturated.
- **Audience.** Women prefer softer tints of blue/green; orange is a least-favorite color for both
  genders when it dominates. → Peach + mint base, coral accent only as a small area.
- **Drawn-on graphics.** Stickers, circles, arrows appear more on winners (41.8% vs 38.1%). → One
  rotated sticker per image, circle around the price in posts.
- **Accessibility.** 4.5:1 for small text, 3:1 for large (W3C). Charcoal on cream = 12:1; white on
  coral = 3.9:1 so coral carries only large text; small CTAs use CORAL_DARK (4.9:1).

## Rules
1. Photo first, price second, headline third. Everything else is small.
2. One face (Mia), one accent, one sticker. If a layout needs two accents, it is wrong.
3. Pastel backgrounds only: peach, mint, cream, lavender. No red or black backgrounds (owner rule).
4. Type: Playfair Display for headlines, Inter for everything else, Caveat for a single handwritten word.
5. Rounded corners (24–48px), soft shadow, white hairline on stickers. Cute, never clinical.
6. Alt text and captions name the product; disclosure on every post.

## Sources
- vidIQ thumbnail study (July 2026): https://vidiq.com/research/youtube-thumbnail-study/
- Eden 507,478-video thumbnail analysis: https://eden.so/blog/what-makes-a-good-youtube-thumbnail/
- Shopify color psychology (isolation effect, gender preferences, W3C ratios): https://www.shopify.com/partners/blog/color-psychology
