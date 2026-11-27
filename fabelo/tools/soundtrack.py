#!/usr/bin/env python3
"""
Fabelo Studio — generic soundtrack builder for any Scribble video.

One JSON spec  ->  character voices (Kokoro, offline) + timed sound effects + background beds
                   + synthesised piano/strings score (ducked under voices) -> muxed MP4 at about -14 LUFS.

  python tools/soundtrack.py --spec film.audio.json --video film_silent.mp4 --models ~/tts --out film_final.mp4

Spec format (all times in seconds):
{
  "duration": 60,
  "voices": {                       # one entry per speaker
    "narrator": {"voice": "af_heart",  "speed": 0.95, "semitones": 0,  "fx": "room",  "gain": 0.85},
    "critic":   {"voice": "am_fenrir", "speed": 0.84, "semitones": -6, "fx": "demon", "gain": 0.95}
  },
  "lines": [["narrator", 1.4, 5.0, "Every time he failed, he crumpled it up."]],   # speaker, start, end, text
  "sfx":   [["crumple", 4.35, 0.5, {"d": 0.9}],                                     # name, at, gain, args
            ["step", 25.9, 0.35, {"every": 0.28, "until": 27.6}]],                  # every/until = repeat
  "beds":  [["rain", 37.4, 52.8, 0.07], ["drone", 6.6, 12.3, 0.10]],               # name, start, end, gain
  "music": {"level": 0.05, "sections": [[0, 30, ["Am","F","C","G"], 4, 64, "sparse", 0.9]],
            "final_chord": true}
}

fx:      none | room | warm | demon | radio | child
SFX:     pop scribble whoosh ding bell chime boing poof step tick clank coin click wood swoop
         crumple rustle paper_land dark_whoosh riser burst hiss whistle thud pluck(note=midi)
         buzz(d) ringback tap
Beds:    drone heartbeat(bpm) rain birds crickets crackle breath
Styles:  sparse dark warm build tension triumph tender
Chords:  Am F C G Dm E Em
Kokoro voices (US English): af_heart af_bella af_nicole af_sarah af_sky · am_michael am_onyx am_fenrir am_puck am_adam am_echo
"""
import argparse, json, os, subprocess, sys, tempfile
import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sfxbase as M  # noqa: E402

SR = M.SR
T = M.t_axis
rng = np.random.default_rng(11)


# ------------------------------------------------------------------ extra effects
def crumple(d=0.9):
    n = int(d * SR); y = np.zeros(n)
    for _ in range(int(d * 70)):
        i = rng.integers(0, max(1, n - 2000)); L = rng.integers(200, 1600)
        seg = M.bandpass(rng.standard_normal(L), 1200, 9000) * np.exp(-np.arange(L) / (L / 3)) * (0.4 + rng.random())
        y[i:i + L] += seg[:len(y[i:i + L])]
    return M.norm(y * np.minimum(1, np.minimum(T(d) / 0.05, (d - T(d)) / 0.15)))
def rustle(d=0.8):
    x = M.bandpass(M.noise(d), 900, 7000); t = T(d)
    return M.norm(x * (0.4 + 0.6 * np.abs(np.sin(2 * np.pi * 5 * t + np.sin(t * 9)))) * np.sin(np.pi * t / d))
def paper_land():
    t = T(0.18)
    return M.norm(M.bandpass(M.noise(0.18), 300, 4000) * M.env_ad(len(t), 0.002, 0.03) + 0.6 * np.sin(2 * np.pi * 140 * t) * M.env_ad(len(t), 0.002, 0.04))
def dark_whoosh(d=1.4):
    t = T(d); y = M.lowpass_var(M.noise(d), 120, 900) * np.sin(np.pi * t / d) ** 2
    return M.norm(y + 0.8 * np.sin(2 * np.pi * (48 - 10 * t / d) * t) * np.sin(np.pi * t / d))
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
def midi(m): return 440 * 2 ** ((m - 69) / 12)
def pluck(note=72):
    f = midi(note); t = T(1.2)
    return M.norm((np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t)) * np.exp(-t / 0.5) * np.minimum(1, t / 0.003))
def buzz(d=1.0):
    # phone on vibrate: two rattling pulses per second
    t = T(d); gate = ((t % 1.0) < 0.38) | (((t % 1.0) > 0.5) & ((t % 1.0) < 0.88))
    y = np.sin(2 * np.pi * 150 * t) * (0.6 + 0.4 * np.sign(np.sin(2 * np.pi * 26 * t))) + 0.3 * M.bandpass(M.noise(d), 200, 1800)
    return M.norm(M.lowpass_var(y * gate, 2400, 2400) * np.minimum(1, (d - t) / 0.05))
def ringback():
    # one outgoing-call ring (US style 440+480 Hz, 2 s)
    t = T(2.0); return M.norm((np.sin(2 * np.pi * 440 * t) + np.sin(2 * np.pi * 480 * t)) * np.minimum(1, np.minimum(t / 0.02, (2.0 - t) / 0.05)))
def tap():
    t = T(0.08); return M.norm(M.bandpass(M.noise(0.08), 1500, 6000) * np.exp(-t / 0.012) + 0.4 * np.sin(2 * np.pi * 900 * t) * np.exp(-t / 0.02))

# beds (length d)
def drone(d):
    t = T(d)
    y = np.sin(2 * np.pi * 41 * t) + 0.6 * np.sin(2 * np.pi * 55.3 * t + np.sin(t * 0.7)) + 0.9 * M.bandpass(M.noise(d), 60, 260)
    return M.norm(y * (0.75 + 0.25 * np.sin(t * 1.3)))
def heartbeat(d, bpm=70):
    out = np.zeros(int(d * SR)); per = 60 / bpm; k = 0.0
    while k < d - 0.3:
        for off, g in ((0, 1.0), (0.22, 0.7)):
            b = np.sin(2 * np.pi * 55 * T(0.14)) * M.env_ad(int(0.14 * SR), 0.004, 0.05)
            j = int((k + off) * SR); out[j:j + len(b)] += b[:max(0, len(out) - j)] * g
        k += per
    return M.norm(out)
def birds(d):
    out = np.zeros(int(d * SR)); k = 0.3
    while k < d - 1:
        f0 = 2600 + rng.random() * 1800; n = int(0.12 * SR); tt = np.arange(n) / SR
        ch = np.sin(2 * np.pi * (f0 + 900 * np.sin(2 * np.pi * 14 * tt)) * tt) * np.sin(np.pi * tt / 0.12)
        for r in range(rng.integers(2, 4)):
            j = int((k + r * 0.15) * SR); out[j:j + n] += ch[:max(0, len(out) - j)]
        k += 1.2 + rng.random() * 2
    return M.norm(out)
def rain(d):
    return M.norm(M.bandpass(M.noise(d), 800, 7000) * 0.5 + M.bandpass(M.noise(d), 150, 600) * 0.3)


SFX = {
    'pop': M.sfx_pop, 'scribble': M.sfx_scribble, 'whoosh': M.sfx_whoosh, 'ding': M.sfx_ding, 'bell': M.sfx_bell,
    'chime': M.sfx_chime, 'boing': M.sfx_boing, 'poof': M.sfx_poof, 'step': M.sfx_step, 'tick': M.sfx_tick,
    'clank': M.sfx_clank, 'coin': M.sfx_coin, 'click': M.sfx_click, 'wood': M.sfx_wood, 'swoop': M.sfx_swoop,
    'crumple': crumple, 'rustle': rustle, 'paper_land': paper_land, 'dark_whoosh': dark_whoosh, 'riser': riser,
    'burst': burst, 'hiss': hiss, 'whistle': whistle, 'thud': thud, 'pluck': pluck,
    'buzz': buzz, 'ringback': ringback, 'tap': tap,
}
SFX_DEFAULT_D = {'scribble': 1.0, 'swoop': 1.0}
BEDS = {'drone': drone, 'heartbeat': heartbeat, 'rain': rain, 'birds': birds,
        'crickets': M.bed_crickets, 'crackle': M.bed_crackle, 'breath': M.bed_breath}


# ------------------------------------------------------------------ music
def piano_note(f, d=3.0):
    t = T(d)
    y = (np.sin(2 * np.pi * f * t) * np.exp(-t / 1.8) + 0.5 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t / 1.0) +
         0.22 * np.sin(2 * np.pi * 3.01 * f * t) * np.exp(-t / 0.6) + 0.1 * np.sin(2 * np.pi * 4.02 * f * t) * np.exp(-t / 0.35))
    return y * np.minimum(1, t / 0.004)
def strings(fs, d):
    t = T(d); vib = 1 + 0.003 * np.sin(2 * np.pi * 5.2 * t)
    return sum(sum(np.sin(2 * np.pi * f * h * vib * t) / h for h in (1, 2, 3)) for f in fs) * np.minimum(1, t / 1.2) * np.minimum(1, (d - t) / 1.2)
CH = {'Am': [57, 60, 64], 'F': [53, 57, 60], 'C': [48, 52, 55, 60], 'G': [55, 59, 62], 'Dm': [50, 53, 57], 'E': [52, 56, 59], 'Em': [52, 55, 59]}
MEL = {'triumph': [76, 74, 72, 74, 76, 79, 77, 76], 'tender': [72, 71, 69, 67], 'warm': [69, 67, 65, 64]}


def score(total, sections, final_chord=True):
    out = np.zeros(int(total * SR))
    def add(sig, at, g):
        j = int(at * SR)
        if 0 <= j < len(out): out[j:j + len(sig)] += sig[:len(out) - j] * g
    for a, b, chords, bpc, bpm, style, g in sections:
        beat = 60 / bpm; t = a; ci = 0
        while t < b - 0.1:
            ch = CH[chords[ci % len(chords)]]; dur = bpc * beat
            if style in ('warm', 'build', 'triumph', 'tender', 'dark'):
                add(strings([midi(n) for n in ch], min(dur + 0.6, b - t + 0.6)), t, 0.010 * g * (1.6 if style == 'triumph' else 1))
            add(piano_note(midi(ch[0] - 12), 4), t, 0.10 * g)
            if style == 'sparse':
                for k, n in enumerate([ch[0], ch[1], ch[2], ch[1]]): add(piano_note(midi(n + 12), 3), t + k * beat, 0.05 * g)
            elif style == 'dark':
                add(piano_note(midi(ch[1]), 3), t + beat * 1.5, 0.05 * g); add(piano_note(midi(ch[2]), 3), t + beat * 3, 0.04 * g)
            elif style == 'warm':
                for k, n in enumerate([ch[0], ch[2], ch[1] + 12, ch[2]]): add(piano_note(midi(n + 12), 3), t + k * beat, 0.055 * g)
                add(piano_note(midi(MEL['warm'][ci % 4] + 12), 3), t + 2 * beat, 0.04 * g)
            elif style == 'build':
                for k in range(int(bpc * 2)): add(piano_note(midi(ch[k % len(ch)] + 12), 2), t + k * beat / 2, 0.05 * g * (1 + (t - a) / max(0.1, b - a)))
            elif style == 'tension':
                for k in range(int(bpc)): add(piano_note(midi(ch[0] - 24), 2.5), t + k * beat, 0.06 * g)
            elif style == 'triumph':
                for k in range(int(bpc * 2)): add(piano_note(midi(ch[k % len(ch)] + 12), 2), t + k * beat / 2, 0.05 * g)
                m = MEL['triumph']; add(piano_note(midi(m[(2 * ci) % 8] + 12), 3), t, 0.07 * g); add(piano_note(midi(m[(2 * ci + 1) % 8] + 12), 3), t + 2 * beat, 0.06 * g)
            elif style == 'tender':
                for k, n in enumerate([ch[0], ch[1], ch[2], ch[1]]): add(piano_note(midi(n + 12), 3), t + k * beat, 0.045 * g)
                add(piano_note(midi(MEL['tender'][ci % 4] + 12), 3.5), t + beat * 2, 0.04 * g)
            t += dur; ci += 1
    if final_chord and total > 4:
        e = total - 3.2
        for n, d_, g in ((48, 0, 0.12), (60, 0, 0.08), (64, 0.1, 0.06), (67, 0.2, 0.06)): add(piano_note(midi(n), 6), e + d_, g)
    tt = T(total)
    return out[:len(tt)] * np.minimum(1, tt / 1.5) * np.minimum(1, np.maximum(0, (total - tt) / 2.5))


# ------------------------------------------------------------------ voices
def ff(inp, out, af):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", inp, "-af", af, "-ar", str(SR), "-ac", "1", out], check=True)


def make_line(k, text, cfg, slot, tmp, idx):
    voice, speed = cfg.get('voice', 'af_heart'), cfg.get('speed', 1.0)
    semis, fx = cfg.get('semitones', 0), cfg.get('fx', 'room')
    for _ in range(4):  # speed up (max 1.25) until the line fits its slot
        s, sr = k.create(text, voice=voice, speed=speed, lang="en-us")
        d = len(s) / sr
        if d <= slot - 0.15 or speed >= 1.25: break
        speed = min(1.25, speed * d / max(0.3, slot - 0.25))
    nz = np.where(np.abs(s) > 0.01)[0]
    if len(nz): s = s[max(0, nz[0] - 240): nz[-1] + 3000]
    raw = os.path.join(tmp, f"r{idx}.wav"); sf.write(raw, s, sr)
    p = 2 ** (semis / 12); chain = []
    if semis: chain.append(f"asetrate={int(sr * p)},aresample={sr},atempo={1 / p:.4f}")
    chain.append({'room': "aecho=0.8:0.6:40|70:0.12|0.07",
                  'warm': "bass=g=4:f=140,aecho=0.8:0.7:50|90:0.14|0.08",
                  'demon': "bass=g=7:f=110,aecho=0.8:0.8:90|180|320:0.35|0.25|0.15",
                  'radio': "highpass=f=400,lowpass=f=3200,acrusher=bits=10:mix=0.2",
                  'child': "treble=g=3"}.get(fx, "anull"))
    out = os.path.join(tmp, f"v{idx}.wav"); ff(raw, out, ",".join(chain))
    x, _ = sf.read(out)
    if fx == 'demon':  # sub-octave layer + grit for monsters / inner critics
        low = os.path.join(tmp, f"l{idx}.wav")
        ff(raw, low, f"asetrate={int(sr * 0.5)},aresample={sr},atempo=2.0,lowpass=f=900,aecho=0.8:0.8:90|180:0.3|0.2")
        y, _ = sf.read(low); n = min(len(x), len(y)); x = x[:n] + 0.55 * y[:n]; x = np.tanh(x * 2.2) / 2.2
    return M.norm(x, 0.8), speed, len(x) / SR


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True); ap.add_argument("--video", required=True)
    ap.add_argument("--models", required=True, help="folder with kokoro-v1.0.int8.onnx + voices-v1.0.bin")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    spec = json.load(open(a.spec, encoding="utf-8"))
    total = float(spec["duration"]); n = int(total * SR)

    voice = np.zeros(n)
    if spec.get("lines"):
        from kokoro_onnx import Kokoro
        k = Kokoro(os.path.join(a.models, "kokoro-v1.0.int8.onnx"), os.path.join(a.models, "voices-v1.0.bin"))
        tmp = tempfile.mkdtemp()
        for i, (who, st, en, text) in enumerate(spec["lines"]):
            cfg = spec["voices"][who]
            x, sp, d = make_line(k, text, cfg, en - st, tmp, i)
            j = int(st * SR); voice[j:j + len(x)] += x[:max(0, n - j)] * cfg.get('gain', 0.9)
            warn = "  <-- longer than its slot, retime the scene" if d > (en - st) + 0.3 else ""
            print(f"  {who:9s} {d:5.2f}s / {en - st:5.2f}s  speed {sp:.2f}  {text}{warn}")

    fx = np.zeros(n)
    def put(sig, at, g):
        j = int(at * SR)
        if 0 <= j < n: fx[j:j + len(sig)] += sig[:n - j] * g
    for e in spec.get("sfx", []):
        name, at, g = e[0], float(e[1]), float(e[2]); args = dict(e[3]) if len(e) > 3 else {}
        every, until = args.pop("every", None), args.pop("until", None)
        if name in SFX_DEFAULT_D and 'd' not in args: args['d'] = SFX_DEFAULT_D[name]
        times = [at] if not every else list(np.arange(at, until, every))
        for t in times: put(SFX[name](**args), t, g)
    for e in spec.get("beds", []):
        name, a0, a1, g = e[0], float(e[1]), float(e[2]), float(e[3]); args = e[4] if len(e) > 4 else {}
        d = a1 - a0; sig = BEDS[name](d, **args); t = T(len(sig) / SR); fd = min(1.0, d / 3)
        put(sig * np.minimum(1, np.minimum(t / fd, (len(sig) / SR - t) / fd)), a0, g)

    mus = np.zeros(n)
    if spec.get("music"):
        m = spec["music"]; mus = score(total, m["sections"], m.get("final_chord", True))
        mus = mus / (np.sqrt(np.mean(mus ** 2)) + 1e-9) * m.get("level", 0.05)

    env = np.convolve(np.abs(voice), np.ones(int(0.3 * SR)) / int(0.3 * SR), mode='same')
    mix = voice + fx * 0.8 + mus * (1 - 0.5 * np.clip(env / 0.05, 0, 1))   # music ducks under voices
    mix = mix * (0.15 / (np.sqrt(np.mean(mix ** 2)) + 1e-9))
    mix = np.clip(np.tanh(mix * 1.2) / 1.2 * 1.05, -0.95, 0.95)
    wav = os.path.splitext(a.out)[0] + ".wav"
    sf.write(wav, np.stack([mix, mix], 1), SR, subtype="PCM_16")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", a.video, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", a.out], check=True)
    r = subprocess.run(["ffmpeg", "-i", a.out, "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    lufs = [l for l in r.splitlines() if l.strip().startswith("I:")]
    print("Saved", a.out, "| loudness", lufs[-1].strip() if lufs else "?")


if __name__ == "__main__":
    main()
