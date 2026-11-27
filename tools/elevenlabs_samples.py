"""Make short ElevenLabs voice samples into samples/elevenlabs/ so a voice can be picked.

Reads the key from the ELEVENLABS_API_KEY environment variable and never prints it.
Each sample reads the same queued Short script, so the voices compare fairly.
"""
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

API = "https://api.elevenlabs.io/v1"
ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "samples" / "elevenlabs"
SCRIPT = ROOT / "scripts" / "queue" / "batch-01-04.json"

# Library voices to compare: name -> (fallback voice id, short note)
VOICES = [
    ("Brian", "nPczCjzI2devNBz1zQrb", "deep American male, narration"),
    ("Daniel", "onwK4e9ZLuTAKqWW03F9", "authoritative British male, news style"),
    ("George", "JBFqnCBsd6RMkjVDRZzb", "warm British male, storyteller"),
    ("Matilda", "XrExE9yKIg1WjnnlVkGX", "warm American female, friendly"),
]
MODEL = "eleven_multilingual_v2"


def call(path, body=None):
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    headers = {"xi-api-key": key, "accept": "*/*"}
    data = None
    if body is not None:
        headers["content-type"] = "application/json"
        data = json.dumps(body).encode()
    req = urllib.request.Request(API + path, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def main():
    if not os.environ.get("ELEVENLABS_API_KEY", "").strip():
        print("::error title=ELEVENLABS_API_KEY missing::Add the ElevenLabs key as the "
              "repository secret ELEVENLABS_API_KEY, then run this again.")
        return 1

    script = json.loads(SCRIPT.read_text())
    text = " ".join(s["text"] for s in script["scenes"])[:900]

    ids = {}
    try:
        listed = json.loads(call("/voices"))
        for v in listed.get("voices", []):
            ids.setdefault(v["name"].split(" ")[0].split("-")[0].strip(), v["voice_id"])
        print("Voices on the account:", ", ".join(sorted(ids)))
    except urllib.error.HTTPError as e:
        print(f"Could not list voices (HTTP {e.code}); using known ids.")

    OUT.mkdir(parents=True, exist_ok=True)
    made = 0
    for name, fallback, note in VOICES:
        vid = ids.get(name, fallback)
        body = {"text": text, "model_id": MODEL,
                "voice_settings": {"stability": 0.45, "similarity_boost": 0.8,
                                   "style": 0.2, "use_speaker_boost": True}}
        try:
            audio = call(f"/text-to-speech/{vid}?output_format=mp3_44100_128", body)
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            print(f"::warning::{name} failed: HTTP {e.code} {detail}")
            continue
        (OUT / f"{name.lower()}.mp3").write_bytes(audio)
        print(f"Made {name} ({note}), {len(audio)} bytes")
        made += 1
    (OUT / "README.md").write_text(
        f"# ElevenLabs samples\n\nScript: {script['title']}\nModel: {MODEL}\n\n"
        + "\n".join(f"- {n.lower()}.mp3: {note}" for n, _, note in VOICES) + "\n")
    return 0 if made else 1


if __name__ == "__main__":
    sys.exit(main())
