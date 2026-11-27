#!/usr/bin/env python3
"""
Lay real sound-effect files (ElevenLabs or any wav) over a mix, by the "sfx_files" list in film.audio.json.

  python3 s2/tools/overlay_files.py --spec <dir>/film.audio.json --dir <dir> --mix <dir>/work/mix.wav --out <dir>/work/mix_sfx.wav

"sfx_files": [[name, start, gain_db, {"cut": s, "fade_in": s, "fade_out": s, "loop_until": s, "pan": -1..1}], ...]
name = file in <dir>/sfx/<name>.wav. Every effect is loudness-matched first (RMS -20 dBFS), then placed with its gain.
"""
import argparse, json, os
import numpy as np
import soundfile as sf

SR = 48000


def load(path):
    x, sr = sf.read(path, always_2d=True)
    if sr != SR:
        n = int(len(x) * SR / sr); idx = np.linspace(0, len(x) - 1, n)
        x = np.stack([np.interp(idx, np.arange(len(x)), x[:, c]) for c in range(x.shape[1])], 1)
    if x.shape[1] == 1: x = np.repeat(x, 2, 1)
    return x[:, :2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--spec', required=True); ap.add_argument('--dir', required=True)
    ap.add_argument('--mix', required=True); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    spec = json.load(open(a.spec, encoding='utf-8'))
    mix, sr = sf.read(a.mix, always_2d=True)
    assert sr == SR, 'mix must be 48 kHz'
    n = len(mix); cache = {}
    for e in spec.get('sfx_files', []):
        name, t0, gdb = e[0], float(e[1]), float(e[2]); o = e[3] if len(e) > 3 else {}
        if name not in cache:
            x = load(os.path.join(a.dir, 'sfx', name + '.wav'))
            rms = np.sqrt(np.mean(x ** 2)) + 1e-9
            cache[name] = x * (10 ** (-20 / 20) / rms)
        x = cache[name].copy()
        if o.get('loop_until'):
            need = int((float(o['loop_until']) - t0) * SR)
            reps = int(np.ceil(need / len(x))) + 1
            x = np.concatenate([x] * reps)[:need]
        if o.get('cut'): x = x[:int(float(o['cut']) * SR)]
        fi, fo = int(o.get('fade_in', 0.005) * SR), int(o.get('fade_out', 0.03) * SR)
        if fi: x[:fi] *= np.linspace(0, 1, fi)[:, None]
        if fo and fo < len(x): x[-fo:] *= np.linspace(1, 0, fo)[:, None]
        p = float(o.get('pan', 0)); x[:, 0] *= min(1, 1 - p); x[:, 1] *= min(1, 1 + p)
        x *= 10 ** (gdb / 20)
        j = int(t0 * SR)
        if j >= n: continue
        L = min(len(x), n - j); mix[j:j + L] += x[:L]
    peak = np.max(np.abs(mix))
    if peak > 0.98: mix *= 0.98 / peak
    sf.write(a.out, mix.astype(np.float32), SR, subtype='FLOAT')
    print(f"overlay → {a.out}  ({len(spec.get('sfx_files', []))} effects)")


if __name__ == '__main__':
    main()
