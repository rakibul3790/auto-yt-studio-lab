#!/usr/bin/env python3
"""
Fabelo Studio v2 — voices FIRST (animatic lock).

Generates every spoken line with Kokoro (offline), polishes it like a dialogue editor would
(high-pass, mud cut, presence, de-ess, gentle compression), measures the REAL length of each
line and estimates word timings from the audio. The scene is then timed to the voice, and the
Shorts captions use the word timings, so mouth, captions and cuts all land exactly.

  python3 v2/tools/voices.py --spec work/<slug>/film.audio.json --models "$FABELO_MODELS" --out work/<slug>/voice

Writes  <out>/line_00.wav …  (48 kHz mono, dry; reverb is added in the mix)
        <out>/timing.json   {"lines":[{"i","speaker","start","dur","end","text","words":[[w,t0,t1],…]}]}

Spec (same file as the mix; v1 style lines work as is). A line's end may be null = auto:
  "voices": {"narrator": {"voice": "af_heart", "speed": 0.92, "semitones": 0, "fx": "clean", "space": "studio", "gain": 0.9}},
  "lines":  [["narrator", 1.2, null, "He folded his first paper plane on a Monday."]]

fx:    clean | warm | radio (phone) | demon (inner critic) | child | whisper
space: none | studio | room | hall      (reverb send used by mix.py)
"""
import argparse, json, os, re, subprocess, sys, tempfile
import numpy as np
import soundfile as sf

SR = 48000
FX = {
    # dialogue polish: rumble cut, mud cut, presence, air, de-ess, gentle compression
    'clean': "highpass=f=85,equalizer=f=260:t=q:w=1.1:g=-2.5,equalizer=f=3300:t=q:w=1.2:g=2.5,"
             "treble=g=1.5:f=9000,deesser=i=0.35,acompressor=threshold=-21dB:ratio=2.6:attack=6:release=90:makeup=2",
    'warm': "highpass=f=70,bass=g=3:f=140,equalizer=f=320:t=q:w=1.2:g=-1.5,equalizer=f=2800:t=q:w=1.4:g=1.5,"
            "deesser=i=0.35,acompressor=threshold=-21dB:ratio=2.4:attack=8:release=110:makeup=2",
    'radio': "highpass=f=420,lowpass=f=3300,equalizer=f=1700:t=q:w=1:g=4,acrusher=bits=11:mix=0.15,"
             "acompressor=threshold=-24dB:ratio=5:attack=3:release=60:makeup=4",
    'demon': "highpass=f=50,bass=g=7:f=110,lowpass=f=6000,acompressor=threshold=-22dB:ratio=4:attack=5:release=120:makeup=3",
    'child': "highpass=f=120,treble=g=3,equalizer=f=3500:t=q:w=1:g=2,deesser=i=0.4,acompressor=threshold=-20dB:ratio=2.5:attack=6:release=90:makeup=2",
    'whisper': "highpass=f=200,equalizer=f=5000:t=q:w=1:g=3,acompressor=threshold=-26dB:ratio=3:attack=4:release=80:makeup=5",
}


def ff(inp, out, af):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", inp, "-af", af, "-ar", str(SR), "-ac", "1", out], check=True)


def trim(s, sr):
    nz = np.where(np.abs(s) > 0.012)[0]
    if not len(nz): return s
    return s[max(0, nz[0] - int(0.012 * sr)): nz[-1] + int(0.09 * sr)]


def word_times(x, text, offset):
    """Estimate per-word times from the audio: split the speech span by syllable weight,
    then snap each boundary to the nearest real pause (energy gap) when one is close."""
    words = text.split()
    hop = int(0.01 * SR)
    env = np.sqrt(np.convolve(x ** 2, np.ones(hop * 3) / (hop * 3), mode='same')[::hop])
    thr = max(0.02, 0.12 * np.percentile(env, 95))
    speech = env > thr
    idx = np.where(speech)[0]
    if not len(idx) or not words:
        return [[w, offset, offset] for w in words]
    a, b = idx[0], idx[-1] + 1
    # gaps of >= 50 ms inside the speech span
    gaps, run = [], None
    for i in range(a, b):
        if not speech[i]:
            run = i if run is None else run
        elif run is not None:
            if i - run >= 5: gaps.append((run + i) / 2)
            run = None

    def weight(w):
        v = len(re.findall(r'[aeiouy]+', w.lower())) or 1
        return v + 0.08 * len(w) + (0.7 if re.search(r'[,;:]$', w) else 1.0 if re.search(r'[.!?…]$', w) else 0)
    ws = np.array([weight(w) for w in words]); cum = np.concatenate([[0], np.cumsum(ws)]) / ws.sum()
    orig = a + cum * (b - a); bounds = orig.copy()
    for k in range(1, len(bounds) - 1):
        if gaps:
            g = min(gaps, key=lambda q: abs(q - orig[k]))
            # snap to a real pause only if neither neighbouring word shrinks below half its share
            if abs(g - orig[k]) <= 14 and g - bounds[k - 1] >= 0.5 * (orig[k] - orig[k - 1]) and orig[k + 1] - g >= 0.5 * (orig[k + 1] - orig[k]):
                bounds[k] = g
    return [[w, round(offset + bounds[i] * 0.01, 3), round(offset + bounds[i + 1] * 0.01, 3)] for i, w in enumerate(words)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True); ap.add_argument("--models", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--max-speed", type=float, default=1.15, help="never speed a voice up beyond this to fit a slot")
    a = ap.parse_args()
    spec = json.load(open(a.spec, encoding="utf-8"))
    os.makedirs(a.out, exist_ok=True)
    from kokoro_onnx import Kokoro
    k = Kokoro(os.path.join(a.models, "kokoro-v1.0.int8.onnx"), os.path.join(a.models, "voices-v1.0.bin"))
    tmp = tempfile.mkdtemp()
    lines, warn = [], []
    L = spec.get("lines", [])
    for i, ln in enumerate(L):
        who, st, en, text = ln[0], float(ln[1]), ln[2], ln[3]
        cfg = spec["voices"][who]
        speed = cfg.get("speed", 1.0)
        slot = (float(en) - st) if en is not None else None
        for _ in range(4):
            s, sr = k.create(text, voice=cfg.get("voice", "af_heart"), speed=speed, lang="en-us")
            s = trim(s, sr); d = len(s) / sr
            if slot is None or d <= slot - 0.1 or speed >= a.max_speed: break
            speed = min(a.max_speed, speed * d / max(0.3, slot - 0.15))
        raw = os.path.join(tmp, f"r{i}.wav"); sf.write(raw, s, sr)
        semis = cfg.get("semitones", 0); p = 2 ** (semis / 12)
        chain = []
        if semis: chain.append(f"asetrate={int(sr * p)},aresample={sr},atempo={1 / p:.4f}")
        chain.append(FX.get(cfg.get("fx", "clean"), FX['clean']))
        out = os.path.join(a.out, f"line_{i:02d}.wav"); ff(raw, out, ",".join(chain))
        x, _ = sf.read(out)
        if cfg.get("fx") == "demon":      # sub-octave layer + grit, like v1, but cleaner
            low = os.path.join(tmp, f"l{i}.wav")
            ff(raw, low, f"asetrate={int(sr * 0.5)},aresample={sr},atempo=2.0,lowpass=f=900")
            y, _ = sf.read(low); n = min(len(x), len(y)); x = x[:n] + 0.5 * y[:n]; x = np.tanh(x * 2.0) / 2.0
        x = x / (np.max(np.abs(x)) + 1e-9) * 0.89
        sf.write(out, x.astype(np.float32), SR, subtype="FLOAT")
        d = len(x) / SR
        words = word_times(x, text, st)
        lines.append({"i": i, "speaker": who, "start": st, "dur": round(d, 3), "end": round(st + d, 3), "text": text,
                      "speed": round(speed, 3), "file": os.path.basename(out), "words": words})
        flag = ""
        if slot is not None and d > slot + 0.25: flag = "  <-- longer than its slot"
        if i + 1 < len(L) and st + d > float(L[i + 1][1]) - 0.12: flag += "  <-- overlaps the next line"
        if flag: warn.append(f"line {i}: {flag.strip()}")
        print(f"  {i:2d} {who:9s} {st:6.2f} → {st + d:6.2f}  ({d:4.2f}s, speed {speed:.2f})  {text}{flag}")
    json.dump({"lines": lines, "warnings": warn}, open(os.path.join(a.out, "timing.json"), "w"), indent=1)
    print(f"timing → {os.path.join(a.out, 'timing.json')}" + (f"  ({len(warn)} warnings)" if warn else ""))


if __name__ == "__main__":
    main()
