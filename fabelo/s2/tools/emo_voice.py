#!/usr/bin/env python3
"""
Free emotional voices with Kokoro (offline). No ElevenLabs, no tokens.

Kokoro has no emotion tags, so the feeling is performed the way a voice director shapes a read:
  * every line is split into phrases; each phrase gets its own speed and pitch
  * real pauses between phrases (the beats where the feeling lands)
  * a soft breath before lines that need one
  * a tone colour per emotion: warm | happy | sad | whisper | hopeful | tense
  * a sad phrase can trail off ("trail": true)
Works for BOTH characters (Classic Scribble and Smooth Scribble) and for the narrator or any role.

  python3 s2/tools/emo_voice.py --spec work/<slug>/film.audio.json --models "$FABELO_MODELS" --out work/<slug>/voice

Spec (the same film.audio.json mix.py reads; mix.py only uses "voices" gain/space/pan from it):
  "voices": {"narrator": {"voice": "af_heart", "speed": 0.92, "semitones": 0, "space": "room", "gain": 0.95}},
  "lines": [
    {"speaker": "narrator", "start": 1.2, "emotion": "warm", "breath": true,
     "phrases": [{"text": "This is Scribble.", "speed": 0.95, "semis": 0.3, "pause": 0.3}]},
    ["narrator", 5.0, null, "A plain v1-style line also works."]
  ]
Phrase keys: text, speed (x voice speed), semis (+ voice semitones), pause (s after), tone (overrides emotion),
             gain, trail.
Writes line_XX.wav (48 kHz mono) + timing.json {"lines":[{i, speaker, start, dur, end, text, emotion, file, words}]}
(words = [[word, t0, t1], …] estimated per phrase, used by S2.caption for word-by-word captions).
"""
import argparse, json, os, re, subprocess, tempfile
import numpy as np
import soundfile as sf

SR = 48000
TONE = {
    'warm':    "highpass=f=75,bass=g=2.5:f=150,equalizer=f=320:t=q:w=1.2:g=-1.5,equalizer=f=2800:t=q:w=1.4:g=1.5",
    'happy':   "highpass=f=85,equalizer=f=300:t=q:w=1.2:g=-2,equalizer=f=3200:t=q:w=1.2:g=3,treble=g=2:f=8500",
    'sad':     "highpass=f=70,bass=g=2:f=160,equalizer=f=2600:t=q:w=1.4:g=-1,lowpass=f=7500",
    'whisper': "highpass=f=160,equalizer=f=900:t=q:w=1:g=-3,equalizer=f=5200:t=q:w=1:g=3.5,lowpass=f=9500",
    'hopeful': "highpass=f=80,bass=g=1.5:f=150,equalizer=f=3000:t=q:w=1.2:g=2.2,treble=g=1.2:f=9000",
    'tense':   "highpass=f=90,equalizer=f=1800:t=q:w=1.2:g=2,acompressor=threshold=-24dB:ratio=3.5:attack=3:release=60:makeup=2",
    'child':   "highpass=f=120,treble=g=3,equalizer=f=3500:t=q:w=1:g=2",
}
POST = "deesser=i=0.35,acompressor=threshold=-21dB:ratio=2.5:attack=7:release=100:makeup=2"
LEVEL = {'warm': 0.88, 'happy': 0.9, 'sad': 0.74, 'whisper': 0.62, 'hopeful': 0.86, 'tense': 0.9, 'child': 0.86}


def ff(inp, out, af):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", inp, "-af", af, "-ar", str(SR), "-ac", "1", out], check=True)


def trim(s, sr):
    nz = np.where(np.abs(s) > 0.01)[0]
    if not len(nz): return s
    return s[max(0, nz[0] - int(0.015 * sr)): nz[-1] + int(0.08 * sr)]


def breath(d=0.36, g=0.045, seed=0):
    rg = np.random.default_rng(seed)
    n = int(d * SR); t = np.arange(n) / SR
    X = np.fft.rfft(rg.standard_normal(n)); f = np.fft.rfftfreq(n, 1 / SR)
    X *= np.exp(-((f - 1700) / 1100) ** 2) + 0.3 * np.exp(-((f - 4200) / 1500) ** 2)
    y = np.fft.irfft(X, n) * np.sin(np.pi * np.clip(t / d, 0, 1)) ** 1.6
    return y / (np.max(np.abs(y)) + 1e-9) * g


def words_in(text, t0, d):
    ws = text.split()
    if not ws: return []
    wt = np.array([(len(re.findall(r'[aeiouy]+', w.lower())) or 1) + 0.08 * len(w) for w in ws])
    cum = np.concatenate([[0], np.cumsum(wt)]) / wt.sum()
    a, b = t0 + 0.04, t0 + max(0.1, d - 0.08)
    return [[w, round(a + cum[i] * (b - a), 3), round(a + cum[i + 1] * (b - a), 3)] for i, w in enumerate(ws)]


def norm_line(ln):
    if isinstance(ln, list):            # v1 style ["speaker", start, end, text]
        return {"speaker": ln[0], "start": float(ln[1]), "emotion": "warm", "phrases": [{"text": ln[3]}]}
    return ln


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True); ap.add_argument("--models", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    spec = json.load(open(a.spec, encoding="utf-8"))
    os.makedirs(a.out, exist_ok=True)
    from kokoro_onnx import Kokoro
    k = Kokoro(os.path.join(a.models, "kokoro-v1.0.int8.onnx"), os.path.join(a.models, "voices-v1.0.bin"))
    tmp = tempfile.mkdtemp()
    out_lines, warn = [], []
    L = [norm_line(x) for x in spec["lines"]]
    for i, ln in enumerate(L):
        voice = spec["voices"][ln["speaker"]]
        emo = ln.get("emotion", "warm")
        parts, words, cur = [], [], 0.0
        if ln.get("breath"):
            b = breath(seed=i, g=0.035 if emo == 'whisper' else 0.045)
            parts += [b, np.zeros(int(0.06 * SR))]; cur += len(b) / SR + 0.06
        for j, ch in enumerate(ln["phrases"]):
            sp = voice.get("speed", 1.0) * ch.get("speed", 1.0)
            s, sr = k.create(ch["text"], voice=voice.get("voice", "af_heart"), speed=sp, lang="en-us")
            s = trim(s, sr)
            raw = os.path.join(tmp, f"r{i}_{j}.wav"); sf.write(raw, s, sr)
            semis = voice.get("semitones", 0) + ch.get("semis", 0); p = 2 ** (semis / 12)
            chain = []
            if abs(semis) > 0.01: chain.append(f"asetrate={int(sr * p)},aresample={sr},atempo={1 / p:.5f}")
            chain.append(TONE[ch.get("tone", voice.get("tone", emo))])
            o = os.path.join(tmp, f"p{i}_{j}.wav"); ff(raw, o, ",".join(chain))
            x, _ = sf.read(o)
            x = x * ch.get("gain", 1.0)
            if ch.get("trail"):
                n = len(x); m = int(min(n, 0.45 * SR)); fade = np.ones(n); fade[-m:] = np.linspace(1, 0.35, m) ** 1.3; x = x * fade
            fi = int(0.008 * SR); x[:fi] *= np.linspace(0, 1, fi); x[-fi:] *= np.linspace(1, 0, fi)
            d = len(x) / SR
            words += words_in(ch["text"], ln["start"] + cur, d)
            pause = ch.get("pause", 0.0)
            parts += [x, np.zeros(int(pause * SR))]; cur += d + pause
        tmpw = os.path.join(tmp, f"l{i}.wav"); sf.write(tmpw, np.concatenate(parts), SR)
        out = os.path.join(a.out, f"line_{i:02d}.wav"); ff(tmpw, out, POST)
        x, _ = sf.read(out)
        x = x / (np.max(np.abs(x)) + 1e-9) * 0.89 * LEVEL.get(emo, 0.88)
        sf.write(out, x.astype(np.float32), SR, subtype="FLOAT")
        d = len(x) / SR
        text = " ".join(c["text"] for c in ln["phrases"])
        out_lines.append({"i": i, "speaker": ln["speaker"], "start": ln["start"], "dur": round(d, 3), "end": round(ln["start"] + d, 3),
                          "text": text, "emotion": emo, "file": os.path.basename(out), "words": words})
        flag = ""
        if i + 1 < len(L) and ln["start"] + d > float(L[i + 1]["start"]) - 0.12: flag = "  <-- overlaps the next line"; warn.append(f"line {i}: overlaps the next line")
        print(f"  {i:2d} {emo:8s} {ln['start']:6.2f} → {ln['start'] + d:6.2f} ({d:4.2f}s)  {text}{flag}")
    json.dump({"lines": out_lines, "warnings": warn}, open(os.path.join(a.out, "timing.json"), "w"), indent=1)
    print(f"timing → {os.path.join(a.out, 'timing.json')}" + (f"  ({len(warn)} warnings)" if warn else ""))


if __name__ == "__main__":
    main()
