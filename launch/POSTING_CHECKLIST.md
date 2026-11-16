# Before and after every Facebook post
1. Only post files that passed post_qa.py AND a fresh strict QA agent. Read caption/link from posts/<name>.txt at posting time, never from earlier output.
2. After posting, read back the live caption and first comment, then run: python verify_post.py <name> "<caption>" "<comment>". Non-zero = fix/delete now.
3. Link preview title in the comment must match the product title.
4. Codes/coupons: show a code ONLY if verified working that day (amazon_local.py coupon check on the Lenovo, or tested by hand). Unverified = no code in the post. Solo/quick posts already skip code-only deals.
5. Price/variant claims (color, size, "was" price) must be on the Amazon page. If unsure, leave the post out.
6. Copy text with `python show_post.py <name>`; after posting run verify_post.py (it writes data/posted_ledger.json).
7. Strict mode: once the Lenovo has run amazon_local.py (v4 data), set POST_QA_STRICT=1 so any product not verified against the live Amazon page in the last 36 h is blocked (price, title, variant, stock, codes).
