"""Make short voice samples to compare voices (run by the Voice samples workflow).

    python tools/voice_samples.py        -> samples/voices/*.mp3
"""
import asyncio
from pathlib import Path

import edge_tts

LINE = ("An octopus has three hearts, and its blood is blue. "
        "When it swims, the heart that serves its body stops beating.")

# (file name, voice, rate, pitch)
VOICES = [
    ("1-christopher-deep", "en-US-ChristopherNeural", "-4%", "-6Hz"),
    ("2-guy-deep", "en-US-GuyNeural", "-4%", "-8Hz"),
    ("3-andrew-deeper", "en-US-AndrewNeural", "-4%", "-10Hz"),
    ("4-roger-deep", "en-US-RogerNeural", "-4%", "-6Hz"),
    ("0-andrew-current", "en-US-AndrewNeural", "+0%", "+0Hz"),
    # women's voices
    ("f1-ava", "en-US-AvaNeural", "+0%", "+0Hz"),
    ("f2-emma", "en-US-EmmaNeural", "+0%", "+0Hz"),
    ("f3-jenny", "en-US-JennyNeural", "+0%", "+0Hz"),
    ("f4-aria", "en-US-AriaNeural", "+0%", "+0Hz"),
]


async def main() -> None:
    out_dir = Path("samples/voices")
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, voice, rate, pitch in VOICES:
        try:
            await edge_tts.Communicate(LINE, voice, rate=rate, pitch=pitch).save(
                str(out_dir / f"{name}.mp3"))
            print("made", name)
        except Exception as e:
            print("FAILED", name, type(e).__name__, e)


asyncio.run(main())
