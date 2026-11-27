#!/usr/bin/env python3
"""
Full soundtrack for a Scribble video: AI voice-over + sound effects + background music,
all timed to the scene, then muxed into the MP4.

  pip install kokoro-onnx soundfile numpy
  (model files: kokoro-v1.0.int8.onnx + voices-v1.0.bin from
   https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0)

  python make_audio.py --video night_silent_1080p.mp4 --lines voice_lines.json --scene scene.json \
                       --voice af_heart --out night_final.mp4

Voices (American English): af_heart, af_bella (female) · am_michael, am_fenrir, am_puck (male).
Everything except the voice is synthesised here, so there are no copyright issues with the sounds or music.
"""
import argparse, json, math, os, subprocess, sys
import numpy as np

SR = 48000
rng = np.random.default_rng(7)


# ------------------------------------------------------------------ helpers
def t_axis(d): return np.arange(int(d * SR)) / SR
def env_ad(n, a=0.005, d=0.2):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / max(d, 1e-4))
def norm(x, peak=1.0):
    m = np.max(np.abs(x)) if len(x) else 0
    return x * (peak / m) if m > 0 else x
def bandpass(x, lo, hi):
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
    X[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(X, len(x))
def lowpass_var(x, start_hz, end_hz):
    y = np.zeros_like(x); s = 0.0
    hz = np.linspace(start_hz, end_hz, len(x))
    a = 1 - np.exp(-2 * np.pi * hz / SR)
    for i in range(len(x)):
        s += a[i] * (x[i] - s); y[i] = s
    return y
def noise(d): return rng.standard_normal(int(d * SR))


# ------------------------------------------------------------------ sound effects (all synthesised)
def sfx_pop():
    t = t_axis(0.09); f = np.linspace(900, 240, len(t))
    return norm(np.sin(2 * np.pi * np.cumsum(f) / SR) * env_ad(len(t), 0.002, 0.03))
def sfx_scribble(d):
    d = max(0.25, d); n = noise(d)
    x = bandpass(n, 1800, 6500)
    t = t_axis(d)
    strokes = np.abs(np.sin(2 * np.pi * (7 + 2 * np.sin(t * 3.1)) * t)) ** 1.5
    fade = np.minimum(1, np.minimum(t / 0.05, (d - t) / 0.08))
    return norm(x * strokes * fade) * 0.8
def sfx_whoosh(d=0.6):
    t = t_axis(d); x = noise(d)
    shape = np.sin(np.pi * t / d) ** 2
    y = lowpass_var(x, 300, 2500) * shape
    return norm(y)
def sfx_ding(f=1320, d=1.2):
    t = t_axis(d)
    y = sum(a * np.sin(2 * np.pi * f * r * t) * np.exp(-t / dec) for r, a, dec in [(1, 1, 0.5), (2.0, 0.35, 0.25), (3.01, 0.15, 0.12)])
    return norm(y * np.minimum(1, t / 0.003))
def sfx_bell(f=300, d=3.0):
    t = t_axis(d)
    parts = [(0.5, 0.6, 1.8), (1, 1, 1.2), (1.19, 0.5, 0.9), (1.5, 0.4, 0.7), (2, 0.35, 0.6), (2.5, 0.2, 0.4), (3, 0.15, 0.3)]
    y = sum(a * np.sin(2 * np.pi * f * r * t) * np.exp(-t / dec) for r, a, dec in parts)
    return norm(y * np.minimum(1, t / 0.004))
def sfx_chime():
    out = np.zeros(int(1.4 * SR))
    for i, f in enumerate([1046.5, 1318.5, 1568.0, 2093.0]):
        s = sfx_ding(f, 1.0) * 0.7; o = int(i * 0.08 * SR)
        out[o:o + len(s)] += s[:len(out) - o]
    return norm(out)
def sfx_boing():
    t = t_axis(0.45); f = 220 + 520 * (1 - np.exp(-t * 9)) + 25 * np.sin(2 * np.pi * 18 * t)
    return norm(np.sin(2 * np.pi * np.cumsum(f) / SR) * env_ad(len(t), 0.004, 0.18))
def sfx_poof():
    d = 0.35; t = t_axis(d)
    y = lowpass_var(noise(d), 1500, 300) * env_ad(len(t), 0.01, 0.09)
    return norm(y)
def sfx_step():
    t = t_axis(0.12)
    y = np.sin(2 * np.pi * 85 * t) * env_ad(len(t), 0.002, 0.03) + 0.25 * bandpass(noise(0.12), 300, 2000) * env_ad(len(t), 0.001, 0.015)
    return norm(y)
def sfx_tick():
    t = t_axis(0.03)
    return norm(np.sin(2 * np.pi * 2400 * t) * env_ad(len(t), 0.0005, 0.006))
def sfx_clank():
    t = t_axis(0.8)
    y = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t / d) for f, a, d in [(523, 1, 0.25), (1187, 0.6, 0.15), (1977, 0.4, 0.08), (3150, 0.2, 0.05)])
    return norm(y * np.minimum(1, t / 0.002))
def sfx_coin():
    a = sfx_ding(1568, 0.6); b = sfx_ding(2093, 0.9)
    out = np.zeros(int(1.0 * SR)); out[:len(a)] += a; o = int(0.09 * SR); out[o:o + len(b)] += b[:len(out) - o]
    return norm(out)
def sfx_click():
    t = t_axis(0.05)
    return norm(bandpass(noise(0.05), 800, 5000) * env_ad(len(t), 0.0005, 0.008))
def sfx_wood():
    t = t_axis(0.25)
    y = np.sin(2 * np.pi * 180 * t) * np.exp(-t / 0.05) + 0.5 * np.sin(2 * np.pi * 410 * t) * np.exp(-t / 0.03)
    return norm(y)
def sfx_swoop(d):
    t = t_axis(d); f = np.linspace(520, 140, len(t))
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / d) ** 2
    return norm(y)
def bed_crickets(d):
    t = t_axis(d); y = np.zeros_like(t)
    k = 0.0
    while k < d:
        dur = 0.16 + rng.random() * 0.1; i0 = int(k * SR); n = int(dur * SR)
        tt = np.arange(n) / SR
        chirp = np.sin(2 * np.pi * (4300 + rng.random() * 400) * tt) * (0.5 + 0.5 * np.sin(2 * np.pi * 32 * tt)) * np.sin(np.pi * tt / dur)
        y[i0:i0 + n] += chirp[:max(0, len(y) - i0)] * (0.6 + 0.4 * rng.random())
        k += 0.55 + rng.random() * 0.9
    return y
def bed_crackle(d):
    n = int(d * SR); y = 0.25 * bandpass(noise(d), 80, 600)
    for _ in range(int(d * 14)):
        i = rng.integers(0, max(1, n - 800)); L = rng.integers(80, 600)
        y[i:i + L] += rng.standard_normal(L) * np.exp(-np.arange(L) / (L / 4)) * (0.5 + rng.random())
    return y
def bed_breath(d):
    t = t_axis(d)
    return lowpass_var(noise(d), 500, 500) * (np.sin(2 * np.pi * t / 3.6) * 0.5 + 0.5) ** 2


# ------------------------------------------------------------------ music (synthesised, ~84 BPM, curious night mood)
def music(total):
    out = np.zeros(int(total * SR))
    beat = 60 / 84; bar = beat * 4
    A, F, Cc, G = 110.0, 87.31, 130.81, 98.0
    prog = [(A, 'm'), (F, 'M'), (Cc, 'M'), (G, 'M')]
    def triad(root, q):
        return [root, root * (1.1892 if q == 'm' else 1.2599), root * 1.4983]
    nbars = int(total / bar) + 1
    for b in range(nbars):
        t0 = b * bar
        root, q = prog[b % 4]; ch = triad(root, q)
        # pad
        n = int((bar + 0.6) * SR); tt = np.arange(n) / SR
        envp = np.minimum(1, tt / 0.6) * np.minimum(1, np.maximum(0, (bar + 0.6 - tt) / 0.6))
        pad = sum(np.sin(2 * np.pi * f * 2 * tt) + 0.5 * np.sin(2 * np.pi * f * 2 * 1.003 * tt) + 0.25 * np.sin(2 * np.pi * f * 4 * tt) for f in ch)
        pad *= envp * 0.05
        i0 = int(t0 * SR); out[i0:i0 + n] += pad[:max(0, len(out) - i0)]
        # bass on 1 and 3
        for k in (0, 2):
            nb = int(0.7 * SR); tb = np.arange(nb) / SR
            bs = np.sin(2 * np.pi * root * tb) * np.exp(-tb / 0.35) * np.minimum(1, tb / 0.01) * 0.16
            j = int((t0 + k * beat) * SR); out[j:j + nb] += bs[:max(0, len(out) - j)]
        # pluck arpeggio (eighth notes), only after the intro
        if t0 >= 7.5:
            pattern = [0, 1, 2, 1, 0, 2, 1, 2]
            for e, idx in enumerate(pattern):
                f = ch[idx] * 4 * (2 if (85.5 <= t0 < 100.5 and e % 2) else 1)
                npl = int(0.6 * SR); tp = np.arange(npl) / SR
                pl = (np.sin(2 * np.pi * f * tp) + 0.4 * np.sin(2 * np.pi * 2 * f * tp) + 0.15 * np.sin(2 * np.pi * 3 * f * tp)) * np.exp(-tp / 0.18) * np.minimum(1, tp / 0.004) * 0.05
                j = int((t0 + e * beat / 2) * SR); out[j:j + npl] += pl[:max(0, len(out) - j)]
        # soft shaker on off-beats in the middle section
        if 15 <= t0 < 111:
            for k in range(4):
                ns = int(0.06 * SR)
                sh = bandpass(noise(0.06), 5000, 11000) * env_ad(ns, 0.002, 0.015) * 0.025
                j = int((t0 + k * beat + beat / 2) * SR); out[j:j + ns] += sh[:max(0, len(out) - j)]
    t = t_axis(total)
    fade = np.minimum(1, t / 2.0) * np.minimum(1, np.maximum(0, (total - t) / 3.0))
    return out[:len(t)] * fade


# ------------------------------------------------------------------ voice
def make_voice(lines, voice, model_dir, total):
    from kokoro_onnx import Kokoro
    k = Kokoro(os.path.join(model_dir, "kokoro-v1.0.int8.onnx"), os.path.join(model_dir, "voices-v1.0.bin"))
    out = np.zeros(int(total * SR))
    for i, ln in enumerate(lines):
        slot = ln["end"] - ln["start"]; speed = 1.0
        for _ in range(4):
            s, sr = k.create(ln["text"], voice=voice, speed=speed, lang="en-us")
            d = len(s) / sr
            if d <= slot - 0.1 or speed >= 1.3: break
            speed = min(1.3, speed * d / (slot - 0.2))
        # trim leading/trailing silence, resample 24k → 48k
        idx = np.where(np.abs(s) > 0.01)[0]
        if len(idx): s = s[max(0, idx[0] - 240): idx[-1] + 2400]
        x = np.interp(np.arange(int(len(s) * SR / sr)) * sr / SR, np.arange(len(s)), s)
        j = int(ln["start"] * SR); out[j:j + len(x)] += x[:max(0, len(out) - j)]
        print(f"  line {i + 1:2d}: {len(x) / SR:5.2f}s in {slot:5.2f}s slot (speed {speed:.2f})")
    return out


# ------------------------------------------------------------------ cue sheet from the scene
def build_sfx(scene, total, sleeps):
    out = np.zeros(int(total * SR))
    def put(sig, at, gain):
        j = int(at * SR)
        if j >= len(out) or j < 0: return
        out[j:j + len(sig)] += sig[:len(out) - j] * gain
    special_pop = {'firecover': (sfx_clank, 0.45), 'lightbulb': (sfx_chime, 0.45), 'money': (sfx_coin, 0.4),
                   'question': (sfx_boing, 0.3), 'dreamcloud': (sfx_chime, 0.25)}
    fires = []
    for p in scene['props']:
        if p['name'] == 'campfire': fires.append((p['at'], p['out'] or total))
        if p['draw'] and p['draw'] > 0:
            put(sfx_scribble(p['draw']), p['at'], 0.22)
            if p['name'] == 'gaslamp': put(sfx_click(), p['at'] + p['draw'], 0.5)
            if p['name'] == 'moon': put(sfx_chime(), p['at'] + 0.3, 0.12)
        else:
            fn, g = special_pop.get(p['name'], (sfx_pop, 0.4))
            put(fn(), p['at'], g)
        if p['name'] == 'woodpile': put(sfx_wood(), 79.8, 0.5); put(sfx_wood(), 80.0, 0.4)
    for a, b in fires:
        put(bed_crackle(b - a) * np.minimum(1, np.minimum(t_axis(b - a) / 0.5, (b - a - t_axis(b - a)) / 0.5)), a, 0.10)
    for tx in scene['texts']:
        if tx['y'] == -385 or (tx['y'] not in (446,) and tx['str'] not in ('DING!', 'DONG!')):
            put(sfx_scribble(min(0.55, tx['write'] or 0.4) + 0.1), tx['at'], 0.12)
        if tx['str'] in ('DING!', 'DONG!'):
            put(sfx_bell(330 if tx['str'] == 'DING!' else 262), tx['at'] - 0.15, 0.32)
    put(sfx_bell(330), 30.8, 0.25)
    for c in scene['chars']:
        if c.get('draw'): put(sfx_scribble(c['draw']['dur']), c['draw']['t0'], 0.3)
        for w in c['walks']:
            step = 0.45 if not w.get('run') else 0.3
            t = w['t0'] + 0.1; n = 0
            while t < w['t1']:
                put(sfx_step(), t, 0.32 if n % 2 else 0.26); t += step; n += 1
        last = None
        for k in c['costume']:
            if k['v'] and k['v'] != last: put(sfx_poof(), k['t'], 0.35)
            last = k['v']
        for k in c['expr']:
            if k['v'] in ('shocked', 'scared'): put(sfx_boing(), k['t'], 0.28)
        for k in c['hold']:
            if k['v']: put(sfx_pop(), k['t'], 0.25)
    # ambience
    def bed(fn, a, b, g):
        d = b - a; x = fn(d); tt = t_axis(d)
        put(x * np.minimum(1, np.minimum(tt / 1.5, (d - tt) / 1.5)), a, g)
    bed(bed_crickets, 7.0, 85.5, 0.035); bed(bed_crickets, 101.0, 111.0, 0.03)
    for a, b in sleeps: bed(bed_breath, a, b, 0.05)
    put(sfx_swoop(5.2), 1.3, 0.10)
    for a, b in [(49.5, 62.9), (100.8, 111.2)]:
        t = a + 0.5
        while t < b: put(sfx_tick(), t, 0.10); t += 1.0
    for t in (39.3, 62.7, 100.4, 111.0): put(sfx_whoosh(0.6), t - 0.2, 0.25)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True); ap.add_argument("--lines", required=True); ap.add_argument("--scene", required=True)
    ap.add_argument("--voice", default="af_heart"); ap.add_argument("--models", default=os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--out", required=True); ap.add_argument("--wav", default=None)
    a = ap.parse_args()
    lines = json.load(open(a.lines))["lines"]; scene = json.load(open(a.scene))
    total = float(json.load(open(a.lines)).get("duration", 120))
    sleeps = [(43.6, 54.6), (58.9, 61.4)]
    cache = os.path.splitext(a.out)[0] + f".{a.voice}.voice.npy"
    if os.path.exists(cache):
        v = np.load(cache); print("voice (cached)")
    else:
        print("voice ...")
        v = make_voice(lines, a.voice, a.models, total); np.save(cache, v)
    v = norm(v, 0.7)
    print("sound effects ...")
    fx = build_sfx(scene, total, sleeps)
    print("music ...")
    m = music(total)
    m = m / (np.sqrt(np.mean(m ** 2)) + 1e-9) * 0.03
    # duck the music under the voice
    env = np.convolve(np.abs(v), np.ones(int(0.25 * SR)) / int(0.25 * SR), mode='same')
    duck = 1 - 0.55 * np.clip(env / 0.05, 0, 1)
    rms = lambda x: 20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9)
    print(f"  levels (dBFS RMS): voice {rms(v):.1f}  fx {rms(fx):.1f}  music {rms(m * duck):.1f}")
    fx = fx * 0.75
    mix = v + fx + m * duck
    mix = mix * (0.16 / (np.sqrt(np.mean(mix ** 2)) + 1e-9))       # loudness target (~ -14 LUFS)
    mix = np.tanh(mix * 1.2) / 1.2 * 1.05                           # soft limiter
    mix = np.clip(mix, -0.95, 0.95)
    stereo = np.stack([mix, mix], axis=1)
    import soundfile as sf
    wav = a.wav or os.path.splitext(a.out)[0] + ".wav"
    sf.write(wav, stereo, SR, subtype="PCM_16")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", a.video, "-i", wav, "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", a.out], check=True)
    print("Saved", a.out)


if __name__ == "__main__":
    main()
