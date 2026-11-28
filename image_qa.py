#!/usr/bin/env python3
"""Vision QA for rendered pin/post images - the gap that let a broken/off-brand pin through.

qa_free.py only reads the caption TEXT. This looks at the actual IMAGE with a vision model
(free, via OmniRoute on the Lenovo) and fails a pin whose picture is wrong: an incomplete
grid (empty cells), an off-brand / adult / novelty / off-topic product, an unreadable price,
or a price that is not actually under the tier cap.

Writes item["image_qa"] = {"status": pass|fail|warn, "issues": [...], "model": ...} into
queue/latest.json. eligible_pins() and approve.py both refuse anything with image_qa=fail.
A model/infra error yields "warn" (not a hard fail) so an outage doesn't block everything -
but warn is surfaced so you can eyeball it.

Runs on the Lenovo (needs OmniRoute). Reads the LOCAL PNG, sends it base64:
    python image_qa.py queue\\latest.json
Env: OMNIROUTE_URL, OMNIROUTE_KEY (same as qa_free), VISION_MODELS (comma list, free first).
"""
import utf8_io  # noqa: F401
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

OR_URL = os.environ.get("OMNIROUTE_URL", "http://localhost:20128/v1").rstrip("/")
OR_KEY = os.environ.get("OMNIROUTE_KEY", "sk-omniroute")
# Vision models to try in order (first that returns a valid verdict wins). Free first.
VISION_MODELS = os.environ.get(
    "VISION_MODELS",
    "openrouter/nvidia/nemotron-3.5-super-vl:free,openrouter/mistralai/pixtral-large-2502,openrouter/google/gemini-3.8-flash",
).split(",")

PROMPT = """You are a strict visual QA reviewer for a "{label}" Amazon-deals Pinterest collage.
Look at the IMAGE and FAIL it if ANY of these is true:
- the product grid has an empty cell or is visually incomplete / unbalanced,
- ANY product is not a mainstream family-friendly item a parent would buy (FAIL adult, crude,
  offensive, gag/novelty, alcohol/weapon, or clearly off-topic items),
- any shown price is unreadable, or any price is not consistent with "{label}".
Otherwise PASS. Reply ONLY compact JSON: {{"verdict":"pass|fail","issues":["<=8 words each"]}}"""


def local_image(image_url):
    i = (image_url or "").find("/pins/")
    if i != -1:
        p = Path(image_url[i + 1:])
        if p.exists():
            return p
    # posts live under webposts/<file>.png referenced as .../posts/<file>.png
    j = (image_url or "").find("/posts/")
    if j != -1:
        p = Path("webposts") / Path(image_url[j + 1:]).name
        if p.exists():
            return p
    return None


def data_uri(path):
    b = Path(path).read_bytes()
    ext = Path(path).suffix.lstrip(".").lower() or "png"
    return f"data:image/{ext};base64," + base64.b64encode(b).decode()


def ask_vision(model, label, img_path):
    body = json.dumps({
        "model": model.strip(),
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": PROMPT.format(label=label)},
            {"type": "image_url", "image_url": {"url": data_uri(img_path)}},
        ]}],
        "temperature": 0, "max_tokens": 200,
    }).encode()
    req = urllib.request.Request(OR_URL + "/chat/completions", body,
                                 {"Authorization": "Bearer " + OR_KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        txt = json.loads(r.read())["choices"][0]["message"]["content"]
    m = re.search(r"\{.*\}", txt, re.S)
    v = json.loads(m.group(0)) if m else {}
    verdict = v.get("verdict")
    if verdict not in ("pass", "fail"):
        raise ValueError("no verdict in: " + txt[:120])
    return {"status": verdict, "issues": [str(x)[:60] for x in (v.get("issues") or [])][:5], "model": model.strip()}


def qa_image(item, label):
    img = local_image(item.get("image_url", ""))
    if not img:
        return {"status": "warn", "issues": ["local image not found"], "model": None}
    last = ""
    for model in VISION_MODELS:
        try:
            return ask_vision(model, label, img)
        except Exception as e:
            last = f"{type(e).__name__}: {str(e)[:80]}"
            continue
    return {"status": "warn", "issues": [f"vision unavailable ({last})"], "model": None}


def tier_label(item):
    t = (item.get("title") or "") + " " + (item.get("caption") or "")
    m = re.search(r"[Uu]nder \$?\d+", t)
    return m.group(0) if m else "Amazon deal"


def main(path):
    q = json.loads(Path(path).read_text())
    n = fails = warns = 0
    for group in ("pins", "posts"):                      # reels are video; handled elsewhere
        for it in q.get(group, []):
            if not it.get("image_url"):
                continue
            res = qa_image(it, tier_label(it))
            it["image_qa"] = res
            n += 1
            fails += res["status"] == "fail"
            warns += res["status"] == "warn"
            print(f"{it.get('id'):12} image_qa={res['status']:4} {('; '.join(res['issues']) if res['issues'] else '')}")
    Path(path).write_text(json.dumps(q, indent=2))
    latest = Path(path).parent / "latest.json"
    if latest != Path(path):
        latest.write_text(json.dumps(q, indent=2))
    print(f"\nimage QA: {n} images, {fails} fail, {warns} warn")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "queue/latest.json")
