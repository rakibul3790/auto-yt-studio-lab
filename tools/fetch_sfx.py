"""Download the sound effects listed in assets/sfx/sources.json (ElevenLabs Sound Effects library).

Only missing files are downloaded, so once they are saved in the repo nothing is fetched again.
Library sounds cost no credits. Run from the repo root: python tools/fetch_sfx.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
SFX = ROOT / "assets" / "sfx"
URL = "https://api.us.elevenlabs.io/v1/shared-sound-generations/{id}/audio"


def main() -> int:
    sources = json.loads((SFX / "sources.json").read_text(encoding="utf-8"))
    got = failed = 0
    for kind, items in sources.items():
        if kind.startswith("_"):
            continue
        for it in items:
            out = SFX / kind / it["file"]
            if out.exists() and out.stat().st_size > 1000:
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            try:
                r = requests.get(URL.format(id=it["id"]), timeout=60)
                r.raise_for_status()
                with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as tmp:
                    tmp.write(r.content)
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp.name, "-ar", "48000",
                                "-b:a", "192k", str(out)], check=True)
                Path(tmp.name).unlink(missing_ok=True)
                got += 1
                print(f"sfx: {kind}/{it['file']} ({len(r.content)} bytes)")
            except Exception as e:  # one missing sound only means the synthesized one is used
                failed += 1
                print(f"sfx: could not fetch {kind}/{it['file']}: {e}", file=sys.stderr)
    print(f"sfx: {got} downloaded, {failed} failed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
