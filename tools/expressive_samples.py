"""Samples of free, more expressive voices (run by the Expressive voices workflow).

    python tools/expressive_samples.py chatterbox   -> samples/expressive/*.mp3
    python tools/expressive_samples.py kokoro
"""
import subprocess
import sys
from pathlib import Path

import soundfile as sf

LINE = ("What happens on Earth in just one second? Around four babies are born. "
        "Lightning strikes the planet about forty times! And the Sun? "
        "It burns through four million tons of itself. Every single second.")

OUT = Path("samples/expressive")


def save(name, audio, sr):
    OUT.mkdir(parents=True, exist_ok=True)
    wav = OUT / f"{name}.wav"
    sf.write(wav, audio, sr)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-b:a", "128k",
                    str(OUT / f"{name}.mp3")], check=True)
    wav.unlink()
    print("made", name, flush=True)


def chatterbox():
    from chatterbox.tts import ChatterboxTTS
    model = ChatterboxTTS.from_pretrained(device="cpu")
    # (file name, emotion strength, pacing): more exaggeration = more dramatic
    for name, exaggeration, cfg in (("c1-chatterbox-natural", 0.5, 0.5),
                                    ("c2-chatterbox-excited", 0.8, 0.35)):
        wav = model.generate(LINE, exaggeration=exaggeration, cfg_weight=cfg)
        save(name, wav.squeeze(0).numpy(), model.sr)


def kokoro():
    import numpy as np
    from kokoro import KPipeline
    pipe = KPipeline(lang_code="a")          # American English
    for name, voice in (("k1-kokoro-heart-woman", "af_heart"), ("k2-kokoro-bella-woman", "af_bella"),
                        ("k3-kokoro-michael-man", "am_michael"), ("k4-kokoro-fenrir-man", "am_fenrir")):
        parts = [np.asarray(audio) for _, _, audio in pipe(LINE, voice=voice, speed=1.0)]
        save(name, np.concatenate(parts), 24000)


if __name__ == "__main__":
    {"chatterbox": chatterbox, "kokoro": kokoro}[sys.argv[1]]()
