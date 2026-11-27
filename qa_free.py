#!/usr/bin/env python3
"""Free-AI QA: score every queue item (pin / post / reel caption) with free-tier models via OmniRoute
(the local gateway on the Lenovo), write verdicts back into queue/<date>.json. No Claude tokens.

OmniRoute exposes an OpenAI-compatible endpoint and falls back across free tiers, then paid Claude
last. Set OMNIROUTE_URL (default http://localhost:4000/v1) and OMNIROUTE_KEY in the env.

Each item gets models:[{model, verdict: pass|warn|fail, note}]. The dashboard shows these; the
publisher refuses to post anything whose worst verdict is `fail`."""
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

OR_URL = os.environ.get("OMNIROUTE_URL", "http://localhost:4000/v1").rstrip("/")
OR_KEY = os.environ.get("OMNIROUTE_KEY", "sk-omniroute")
# Compliance QA models. OmniRoute routes/falls back. Keep 2+ for the "two fresh models" rule.
MODELS = os.environ.get("QA_MODELS", "gemini-1.5-flash,llama-3.1-70b,mixtral-8x7b").split(",")
# The judge is an INDEPENDENT channel: different models from QA, so nothing grades its own work.
JUDGE_MODELS = os.environ.get("JUDGE_MODELS", "qwen-2.5-72b,deepseek-chat,command-r-plus").split(",")

RUBRIC = """You are a strict compliance + quality reviewer for an Amazon Associates deal post.
Check ONLY these and reply as compact JSON {{"verdict":"pass|warn|fail","note":"<=12 words"}}:
- Has an #ad / disclosure and "As an Amazon Associate" somewhere: if missing -> fail.
- States a price without an Amazon read time/date -> warn.
- Any absolute or unverifiable claim ("lowest ever", "cheapest", fake urgency) -> fail.
- Knife/weapon, medical, or kids-targeted unsafe content -> fail.
- Misspelling of the product or brand, or a price that looks wrong -> warn.
- Otherwise -> pass.
Item type: {type}. Caption:
<<<
{caption}
>>>"""


def ask(model, item):
    body = json.dumps({
        "model": model.strip(),
        "messages": [{"role": "user", "content": RUBRIC.format(type=item.get("type"), caption=item.get("caption", ""))}],
        "temperature": 0, "max_tokens": 120,
    }).encode()
    req = urllib.request.Request(OR_URL + "/chat/completions", body,
                                {"Authorization": "Bearer " + OR_KEY, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            txt = json.loads(r.read())["choices"][0]["message"]["content"]
        m = re.search(r"\{.*\}", txt, re.S)
        v = json.loads(m.group(0)) if m else {}
        verdict = v.get("verdict", "warn")
        if verdict not in ("pass", "warn", "fail"):
            verdict = "warn"
        return {"model": model.strip(), "verdict": verdict, "note": (v.get("note") or "")[:80]}
    except Exception as e:
        return {"model": model.strip(), "verdict": "warn", "note": f"qa unavailable ({type(e).__name__})"}


JUDGE_BAR = int(os.environ.get("JUDGE_BAR", "9"))
JUDGE = """You are a strict judge scoring an Amazon deal {type} for how well it will perform, against
what high-reach deal content does. Score 0-10 and reply as compact JSON {{"score":N,"note":"<=12 words"}}:
- Hook in the first line, specific benefit + exact price, clear call to action.
- Caption is snappy, not a wall of text; one genuine question is a plus.
- For a reel/pin: the first thing seen is the product (in use), not a wall of text.
- Honest (has disclosure, read-time on price) — dishonest or spammy caps the score at 4.
Caption:
<<<
{caption}
>>>"""


def judge_one(model, item):
    body = json.dumps({"model": model.strip(),
                       "messages": [{"role": "user", "content": JUDGE.format(type=item.get("type"), caption=item.get("caption", ""))}],
                       "temperature": 0, "max_tokens": 80}).encode()
    req = urllib.request.Request(OR_URL + "/chat/completions", body,
                                {"Authorization": "Bearer " + OR_KEY, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            txt = json.loads(r.read())["choices"][0]["message"]["content"]
        v = json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
        return {"model": model.strip(), "score": max(0, min(10, float(v.get("score", 0)))), "note": (v.get("note") or "")[:80]}
    except Exception as e:
        return {"model": model.strip(), "score": None, "note": f"judge unavailable ({type(e).__name__})"}


def qa_item(item):
    models = [ask(m, item) for m in MODELS]
    worst = max(models, key=lambda x: ["pass", "warn", "fail"].index(x["verdict"]))["verdict"]
    item["qa"] = {"status": worst, "models": models}
    # judge: INDEPENDENT models (not the QA set) score 0-10; bar JUDGE_BAR to be eligible
    jl = [judge_one(m, item) for m in JUDGE_MODELS]
    nums = [x["score"] for x in jl if x["score"] is not None]
    mean = round(sum(nums) / len(nums), 1) if nums else None
    item["judge"] = {"score": mean, "bar": JUDGE_BAR, "pass": (mean is not None and mean >= JUDGE_BAR), "models": jl}
    return item


def main(path):
    q = json.loads(Path(path).read_text())
    for group in ("pins", "posts", "reels"):
        q[group] = [qa_item(it) for it in q.get(group, [])]
    Path(path).write_text(json.dumps(q, indent=2))
    (Path(path).parent / "latest.json").write_text(json.dumps(q, indent=2))
    fails = sum(1 for g in ("pins", "posts", "reels") for it in q[g] if it["qa"]["status"] == "fail")
    print(f"QA done: {sum(len(q[g]) for g in ('pins','posts','reels'))} items, {fails} fail")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "queue/latest.json")
