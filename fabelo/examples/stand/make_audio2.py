#!/usr/bin/env python3
"""
Soundtrack for "Stand On Your Mistakes": character voices (Kokoro, offline) with per-character
processing, hand-placed sound effects, and a synthesised emotional piano + strings score.

  python make_audio2.py --video stand_silent_1080p.mp4 --scene stand.src.html --models ../tts --out stand_final.mp4
"""
import argparse, json, os, re, subprocess, sys, tempfile
import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools"))
import sfxbase as M  # reuse the effect synthesisers

SR = M.SR
rng = np.random.default_rng(11)
T = M.t_axis

# ------------------------------------------------------------ voices
VOICES = {  # kokoro voice, speed, pitch semitones, extra fx
    'narrator': ('af_heart', 0.95, 0, 'room'),
    'grandpa': ('am_onyx', 0.88, -2, 'warm'),
    'critic': ('am_fenrir', 0.84, -6, 'demon'),
    'judge': ('af_bella', 1.0, 0, 'room'),
    'coach': ('am_puck', 1.0, -1, 'room'),
}


def ff(inp, out, af):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", inp, "-af", af, "-ar", str(SR), "-ac", "1", out], check=True)


def make_line(k, text, who, slot, tmp, idx):
    voice, speed, semis, fx = VOICES[who]
    for _ in range(4):
        s, sr = k.create(text, voice=voice, speed=speed, lang="en-us")
        d = len(s) / sr
        if d <= slot - 0.15 or speed >= 1.25: break
        speed = min(1.25, speed * d / (slot - 0.25))
    idx_ = np.where(np.abs(s) > 0.01)[0]
    if len(idx_): s = s[max(0, idx_[0] - 240): idx_[-1] + 3000]
    raw = os.path.join(tmp, f"r{idx}.wav"); sf.write(raw, s, sr)
    p = 2 ** (semis / 12)
    chain = []
    if semis: chain.append(f"asetrate={int(sr * p)},aresample={sr},atempo={1 / p:.4f}")
    if fx == 'room': chain.append("aecho=0.8:0.6:40|70:0.12|0.07")
    if fx == 'warm': chain.append("bass=g=4:f=140,aecho=0.8:0.7:50|90:0.14|0.08")
    if fx == 'demon': chain.append("bass=g=7:f=110,aecho=0.8:0.8:90|180|320:0.35|0.25|0.15")
    out = os.path.join(tmp, f"v{idx}.wav")
    ff(raw, out, ",".join(chain) if chain else "anull")
    x, _ = sf.read(out)
    if fx == 'demon':  # add a sub-octave layer + grit
        low = os.path.join(tmp, f"l{idx}.wav")
        ff(raw, low, f"asetrate={int(sr * 0.5)},aresample={sr},atempo=2.0,lowpass=f=900,aecho=0.8:0.8:90|180:0.3|0.2")
        y, _ = sf.read(low); n = min(len(x), len(y)); x = x[:n] + 0.55 * y[:n]
        x = np.tanh(x * 2.2) / 2.2
    return M.norm(x, 0.8), speed


# ------------------------------------------------------------ extra effects for this film
def crumple(d=0.9):
    n = int(d * SR); y = np.zeros(n)
    for _ in range(int(d * 70)):
        i = rng.integers(0, n - 2000); L = rng.integers(200, 1600)
        y[i:i + L] += M.bandpass(rng.standard_normal(L), 1200, 9000) * np.exp(-np.arange(L) / (L / 3)) * (0.4 + rng.random())
    return M.norm(y * np.minimum(1, np.minimum(T(d) / 0.05, (d - T(d)) / 0.15)))
def rustle(d=0.8):
    x = M.bandpass(M.noise(d), 900, 7000); t = T(d)
    mod = 0.4 + 0.6 * np.abs(np.sin(2 * np.pi * 5 * t + np.sin(t * 9)))
    return M.norm(x * mod * np.sin(np.pi * t / d))
def paper_land():
    t = T(0.18)
    return M.norm(M.bandpass(M.noise(0.18), 300, 4000) * M.env_ad(len(t), 0.002, 0.03) + 0.6 * np.sin(2 * np.pi * 140 * t) * M.env_ad(len(t), 0.002, 0.04))
def dark_whoosh(d=1.4):
    t = T(d); y = M.lowpass_var(M.noise(d), 120, 900) * np.sin(np.pi * t / d) ** 2
    sub = np.sin(2 * np.pi * (48 - 10 * t / d) * t) * np.sin(np.pi * t / d)
    return M.norm(y + 0.8 * sub)
def drone(d):
    t = T(d)
    y = np.sin(2 * np.pi * 41 * t) + 0.6 * np.sin(2 * np.pi * 55.3 * t + np.sin(t * 0.7)) + 0.3 * M.bandpass(M.noise(d), 60, 260) * 3
    return M.norm(y * (0.75 + 0.25 * np.sin(t * 1.3)))
def heartbeat(d, bpm=70):
    out = np.zeros(int(d * SR)); per = 60 / bpm; k = 0.0
    beat = lambda: np.sin(2 * np.pi * 55 * T(0.14)) * M.env_ad(int(0.14 * SR), 0.004, 0.05)
    while k < d - 0.3:
        for off, g in ((0, 1.0), (0.22, 0.7)):
            j = int((k + off) * SR); b = beat(); out[j:j + len(b)] += b[:max(0, len(out) - j)] * g
        k += per
    return M.norm(out)
def riser(d=0.8):
    t = T(d); f = 200 + 1200 * (t / d) ** 2
    return M.norm((np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.5 + M.bandpass(M.noise(d), 2000, 9000) * 0.6) * (t / d) ** 2)
def burst():
    d = 2.2; t = T(d)
    boom = np.sin(2 * np.pi * (70 - 30 * t / d) * t) * np.exp(-t / 0.5)
    shimmer = sum(np.sin(2 * np.pi * f * t) * np.exp(-t / 1.2) for f in (1046, 1318, 1568, 2093, 2637)) * 0.25
    return M.norm(boom + shimmer + M.bandpass(M.noise(d), 300, 6000) * np.exp(-t / 0.25) * 0.8)
def hiss(d=1.4):
    t = T(d); return M.norm(M.lowpass_var(M.noise(d), 6000, 400) * (1 - t / d))
def whistle():
    t = T(0.6); f = 2800 + 120 * np.sin(2 * np.pi * 38 * t)
    return M.norm(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.minimum(1, t / 0.02) * np.minimum(1, (0.6 - t) / 0.08))
def thud():
    t = T(0.5); return M.norm(np.sin(2 * np.pi * (75 - 30 * t) * t) * np.exp(-t / 0.12) + M.bandpass(M.noise(0.5), 100, 1500) * np.exp(-t / 0.05) * 0.6)
def pluck(f):
    t = T(1.2); return M.norm((np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t)) * np.exp(-t / 0.5) * np.minimum(1, t / 0.003))
def birds(d):
    out = np.zeros(int(d * SR)); k = 0.3
    while k < d - 1:
        f0 = 2600 + rng.random() * 1800; n = int(0.12 * SR); tt = np.arange(n) / SR
        ch = np.sin(2 * np.pi * (f0 + 900 * np.sin(2 * np.pi * 14 * tt)) * tt) * np.sin(np.pi * tt / 0.12)
        for r in range(rng.integers(2, 4)):
            j = int((k + r * 0.15) * SR); out[j:j + n] += ch[:max(0, len(out) - j)]
        k += 1.2 + rng.random() * 2
    return out
def rain(d):
    t = T(d); return M.bandpass(M.noise(d), 800, 7000) * 0.5 + M.bandpass(M.noise(d), 150, 600) * 0.3


# ------------------------------------------------------------ piano + strings score
def piano_note(f, d=3.0):
    t = T(d)
    y = (np.sin(2 * np.pi * f * t) * np.exp(-t / 1.8) + 0.5 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t / 1.0) +
         0.22 * np.sin(2 * np.pi * 3.01 * f * t) * np.exp(-t / 0.6) + 0.1 * np.sin(2 * np.pi * 4.02 * f * t) * np.exp(-t / 0.35))
    return y * np.minimum(1, t / 0.004)
def strings(fs, d):
    t = T(d); vib = 1 + 0.003 * np.sin(2 * np.pi * 5.2 * t)
    y = sum(sum(np.sin(2 * np.pi * f * h * vib * t) / h for h in (1, 2, 3)) for f in fs)
    return y * np.minimum(1, t / 1.2) * np.minimum(1, (d - t) / 1.2)
N = lambda name: 440 * 2 ** ((name - 69) / 12)  # midi → Hz
CH = {'Am': [57, 60, 64], 'F': [53, 57, 60], 'C': [48, 52, 55, 60], 'G': [55, 59, 62], 'Dm': [50, 53, 57], 'E': [52, 56, 59], 'Em': [52, 55, 59]}


def score(total):
    out = np.zeros(int(total * SR))
    def add(sig, at, g):
        j = int(at * SR)
        if 0 <= j < len(out): out[j:j + len(sig)] += sig[:len(out) - j] * g
    # sections: (start, end, chords, beats per chord, bpm, style, gain)
    secs = [
        (0.0, 37.5, ['Am', 'F', 'C', 'G'], 4, 64, 'sparse', 0.9),
        (37.5, 52.6, ['Am', 'Dm', 'Am', 'E'], 4, 56, 'dark', 0.8),
        (52.6, 78.0, ['F', 'C', 'G', 'Am'], 4, 64, 'warm', 0.9),
        (78.0, 84.0, ['C', 'G', 'Am', 'F'], 2, 76, 'build', 1.0),
        (84.0, 91.0, ['Am'], 8, 60, 'tension', 0.6),
        (91.0, 111.6, ['C', 'G', 'Am', 'F'], 4, 76, 'triumph', 1.15),
        (111.6, 137.0, ['C', 'Am', 'F', 'G'], 4, 66, 'tender', 0.85),
    ]
    melody = {'triumph': [76, 74, 72, 74, 76, 79, 77, 76], 'tender': [72, 71, 69, 67], 'warm': [69, 67, 65, 64]}
    for a, b, chords, bpc, bpm, style, g in secs:
        beat = 60 / bpm; t = a; ci = 0
        while t < b - 0.1:
            ch = CH[chords[ci % len(chords)]]; dur = bpc * beat
            if style in ('warm', 'build', 'triumph', 'tender', 'dark'):
                add(strings([N(n) for n in ch], min(dur + 0.6, b - t + 0.6)), t, 0.010 * g * (1.6 if style == 'triumph' else 1))
            add(piano_note(N(ch[0] - 12), 4), t, 0.10 * g)                     # bass note
            if style == 'sparse':
                for k, n in enumerate([ch[0], ch[1], ch[2], ch[1]]):
                    add(piano_note(N(n + 12), 3), t + k * beat, 0.05 * g)
            elif style == 'dark':
                add(piano_note(N(ch[1]), 3), t + beat * 1.5, 0.05 * g); add(piano_note(N(ch[2]), 3), t + beat * 3, 0.04 * g)
            elif style == 'warm':
                for k, n in enumerate([ch[0], ch[2], ch[1] + 12, ch[2]]):
                    add(piano_note(N(n + 12), 3), t + k * beat, 0.055 * g)
                add(piano_note(N(melody['warm'][ci % 4] + 12), 3), t + 2 * beat, 0.04 * g)
            elif style == 'build':
                for k in range(int(bpc * 2)):
                    add(piano_note(N(ch[k % len(ch)] + 12), 2), t + k * beat / 2, 0.05 * g * (1 + (t - a) / (b - a)))
            elif style == 'tension':
                for k in range(int(bpc)):
                    add(piano_note(N(ch[0] - 24), 2.5), t + k * beat, 0.06 * g)
            elif style == 'triumph':
                for k in range(int(bpc * 2)):
                    add(piano_note(N(ch[k % len(ch)] + 12), 2), t + k * beat / 2, 0.05 * g)
                m = melody['triumph']; add(piano_note(N(m[(2 * ci) % 8] + 12), 3), t, 0.07 * g); add(piano_note(N(m[(2 * ci + 1) % 8] + 12), 3), t + 2 * beat, 0.06 * g)
            elif style == 'tender':
                for k, n in enumerate([ch[0], ch[1], ch[2], ch[1]]):
                    add(piano_note(N(n + 12), 3), t + k * beat, 0.045 * g)
                add(piano_note(N(melody['tender'][ci % 4] + 12), 3.5), t + beat * 2, 0.04 * g)
            t += dur; ci += 1
    add(piano_note(N(48), 6), 134.0, 0.12); add(piano_note(N(60), 6), 134.0, 0.08); add(piano_note(N(64), 6), 134.1, 0.06); add(piano_note(N(67), 6), 134.2, 0.06)
    tt = T(total)
    return out[:len(tt)] * np.minimum(1, tt / 1.5) * np.minimum(1, np.maximum(0, (total - tt) / 2.5))


# ------------------------------------------------------------ cue sheet (hand-placed)
def cues(total):
    out = np.zeros(int(total * SR))
    def put(sig, at, g):
        j = int(at * SR)
        if 0 <= j < len(out): out[j:j + len(sig)] += sig[:len(out) - j] * g
    def bed(sig, a, gain, fade=1.0):
        d = len(sig) / SR; t = T(d); put(sig * np.minimum(1, np.minimum(t / fade, (d - t) / fade)), a, gain)
    # scene 1
    put(M.sfx_scribble(1.4), 0.8, 0.28); put(M.sfx_scribble(1.0), 0.6, 0.12)
    put(crumple(0.9), 4.35, 0.5); put(M.sfx_whoosh(0.4), 5.45, 0.25); put(paper_land(), 6.12, 0.4)
    # critic appearances (dark whoosh + drone while visible)
    for a, b, g in [(6.6, 12.3, 0.10), (17.4, 24.9, 0.10), (32.0, 37.2, 0.10), (38.0, 53.6, 0.14), (84.0, 91.0, 0.16)]:
        put(dark_whoosh(1.4), a - 0.2, 0.5); bed(drone(b - a), a, g, 0.8)
    # scene 2
    put(M.sfx_whoosh(0.6), 12.2, 0.25); put(M.sfx_scribble(0.6), 12.7, 0.15)
    put(crumple(0.8), 22.25, 0.5); put(M.sfx_whoosh(0.4), 23.25, 0.25); put(paper_land(), 23.92, 0.4); put(paper_land(), 24.18, 0.3)
    # scene 3
    put(M.sfx_whoosh(0.6), 24.8, 0.25); put(whistle(), 25.5, 0.35)
    t = 25.9
    while t < 27.6: put(M.sfx_step(), t, 0.35); t += 0.28
    put(thud(), 27.95, 0.7); put(M.sfx_boing(), 27.7, 0.15)
    put(rustle(0.4), 32.0, 0.25); put(crumple(0.8), 35.55, 0.5); put(M.sfx_whoosh(0.4), 36.45, 0.25); put(paper_land(), 37.08, 0.4)
    # scene 4: rain, clock, pile growing
    bed(rain(15.4), 37.4, 0.07, 1.5)
    for i in range(10): put(paper_land(), 37.6 + i * 0.1, 0.12)
    t = 38.5
    while t < 52.4: put(M.sfx_tick(), t, 0.08); t += 1.0
    put(rustle(0.5), 50.8, 0.2)
    t = 51.25
    while t < 52.4: put(M.sfx_step(), t, 0.25); t += 0.42
    # scene 5: grandpa + light
    put(M.sfx_chime(), 52.6, 0.18); put(M.sfx_swoop(1.2) * 0, 52.6, 0)
    t = 53.1
    while t < 55.6: put(M.sfx_step(), t, 0.22); t += 0.6
    put(M.sfx_clank() * 0.3, 57.9, 0.2); put(rustle(0.4), 58.25, 0.3); put(rustle(1.0), 59.45, 0.4)
    put(paper_land(), 64.35, 0.5)
    scale = [60, 62, 64, 67, 69, 72, 74, 76]
    for i in range(8):
        at = 64.4 if i == 0 else 65.1 + i * 0.55
        put(pluck(M_note(scale[i])), at, 0.16); put(rustle(0.25), at - 0.05, 0.18)
    t = 64.95
    while t < 66.3: put(M.sfx_step(), t, 0.2); t += 0.6
    put(M.sfx_chime(), 74.6, 0.25); put(riser(1.0), 73.6, 0.05)
    t = 75.85
    while t < 77.9: put(M.sfx_step(), t, 0.28); t += 0.45
    # scene 6: climb
    for i in range(4): put(thud(), 79.4 + i * 1.0, 0.25); put(pluck(M_note(60 + 2 * i)), 79.4 + i * 1.0, 0.08)
    bed(heartbeat(6.6, 78), 84.1, 0.35, 0.3)
    put(riser(0.8), 90.2, 0.35); put(burst(), 91.0, 0.75); put(hiss(1.5), 91.1, 0.3)
    for i in range(4): put(thud(), 93.2 + i * 0.75, 0.28); put(pluck(M_note(67 + 2 * i)), 93.2 + i * 0.75, 0.1)
    put(M.sfx_chime(), 96.3, 0.3); put(thud(), 99.75, 0.2); put(M.sfx_chime(), 107.3, 0.2)
    # scene 8
    put(M.sfx_whoosh(0.7), 111.3, 0.3); bed(birds(24.0), 112.2, 0.05, 2.0)
    put(crumple(0.7), 113.0, 0.4); put(M.sfx_whoosh(0.35), 113.95, 0.2); put(paper_land(), 114.48, 0.35)
    t = 114.7
    while t < 116.6: put(M.sfx_step(), t, 0.25); t += 0.45
    put(rustle(0.4), 117.1, 0.3); put(rustle(0.9), 118.4, 0.4); put(paper_land(), 119.65, 0.45); put(pluck(M_note(72)), 119.7, 0.15)
    put(M.sfx_step(), 121.5, 0.25); put(M.sfx_step(), 121.95, 0.2); put(M.sfx_chime(), 122.4, 0.2)
    put(M.sfx_chime(), 126.85, 0.25); put(M.sfx_pop(), 130.8, 0.3)
    return out
def M_note(m): return 440 * 2 ** ((m - 69) / 12)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True); ap.add_argument("--scene", required=True)
    ap.add_argument("--models", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    total = 137.0
    lines = json.load(open(a.scene, encoding="utf-8"))  # lines.json exported from the scene's LINES
    cache = os.path.splitext(a.out)[0] + ".voices.npy"
    if os.path.exists(cache):
        v = np.load(cache); print("voices (cached)")
    else:
        from kokoro_onnx import Kokoro
        k = Kokoro(os.path.join(a.models, "kokoro-v1.0.int8.onnx"), os.path.join(a.models, "voices-v1.0.bin"))
        tmp = tempfile.mkdtemp(); v = np.zeros(int(total * SR))
        for i, (who, st, en, text) in enumerate(lines):
            x, sp = make_line(k, text, who, en - st, tmp, i)
            g = {'critic': 0.95, 'grandpa': 1.0, 'narrator': 0.85, 'judge': 0.8, 'coach': 0.8}[who]
            j = int(st * SR); v[j:j + len(x)] += x[:max(0, len(v) - j)] * g
            print(f"  {who:8s} {len(x) / SR:5.2f}s / {en - st:5.2f}s  speed {sp:.2f}  {text}")
        np.save(cache, v)
    fx = cues(total) * 0.8
    m = score(total); m = m / (np.sqrt(np.mean(m ** 2)) + 1e-9) * 0.05
    env = np.convolve(np.abs(v), np.ones(int(0.3 * SR)) / int(0.3 * SR), mode='same')
    duck = 1 - 0.5 * np.clip(env / 0.05, 0, 1)
    mix = v + fx + m * duck
    mix = mix * (0.15 / (np.sqrt(np.mean(mix ** 2)) + 1e-9))
    mix = np.clip(np.tanh(mix * 1.2) / 1.2 * 1.05, -0.95, 0.95)
    wav = os.path.splitext(a.out)[0] + ".wav"
    sf.write(wav, np.stack([mix, mix], 1), SR, subtype="PCM_16")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", a.video, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", a.out], check=True)
    print("Saved", a.out)


if __name__ == "__main__":
    main()
