"""Makes the same short Reel script in several free voices so you can pick one.
Run from GitHub: Actions -> "Voice samples" -> Run workflow. Listen in Releases -> "Voice samples".
"""
import asyncio
from pathlib import Path

import edge_tts

SCRIPT = ("Okay, you need to see this! This heated hand massager has six heat and pressure levels, "
          "and it's rechargeable. It's usually fifty nine dollars. And right now? It's only twenty nine ninety nine! "
          "Hurry, deals like this go fast. The link is waiting for you at Mom Found It Cheaper.")
VOICES = {
    "1-Ava-warm-expressive": "en-US-AvaMultilingualNeural",
    "2-Emma-cheerful-friendly": "en-US-EmmaMultilingualNeural",
    "3-Aria-bright-confident": "en-US-AriaNeural",
    "4-Jenny-current-voice": "en-US-JennyNeural",
    "5-Michelle-soft-soothing": "en-US-MichelleNeural",
}


async def main():
    out = Path("voices")
    out.mkdir(exist_ok=True)
    for name, voice in VOICES.items():
        await edge_tts.Communicate(SCRIPT, voice, rate="+6%", pitch="+2Hz").save(str(out / f"{name}.mp3"))
        print("made", name)

asyncio.run(main())
