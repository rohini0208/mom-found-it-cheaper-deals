"""Check what is LIVE on Facebook against what we generated.
Usage: python verify_post.py post_single "<live caption text>" "<live comment text>"
Exit 1 = mismatch -> fix or delete the post before moving on."""
import json
import re
import sys

TAG = "momfounditc08-20"


def main(name, caption, comment):
    man = {m["file"]: m for m in json.loads(open("posts/manifest.json").read())}
    m = man.get(name)
    if not m:
        sys.exit(f"FAIL: {name} not in manifest")
    want = {i["asin"] for i in m["items"]}
    got = re.findall(r"amazon\.com/dp/([A-Z0-9]{10})\?tag=([a-z0-9-]+)", comment)
    bad = []
    if {a for a, _ in got} != want:
        bad.append(f"ASIN mismatch: live {sorted(a for a, _ in got)} vs expected {sorted(want)}")
    if any(t != TAG for _, t in got):
        bad.append("wrong or missing affiliate tag")
    exp_cap = open(f"posts/{name}.txt").read().split("FIRST COMMENT")[0].replace("CAPTION:", "").strip()
    norm = lambda s: re.sub(r"\s+", " ", s.replace("’", "'")).strip()
    if norm(exp_cap) not in norm(caption):
        bad.append("live caption differs from generated caption")
    if "Amazon Associate" not in caption:
        bad.append("disclosure missing")
    for i in m["items"]:                     # a price/claim in the caption must match the data
        p = i.get("price") or ""
        if p and p not in caption and name.startswith("post_q"):
            bad.append(f"price {p} not in caption")
    print("\n".join(("FAIL: " + b) for b in bad) or "OK: live post matches data")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main(*sys.argv[1:4])
