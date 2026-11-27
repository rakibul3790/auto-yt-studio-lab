#!/usr/bin/env python3
"""
Fabelo Studio v2 — professional stereo mix.

Reads the SAME spec as voices.py plus the film's cues (cuts and transitions dumped by record2.js),
and builds a stereo mix with separate stems:

  dialogue  polished lines from voices.py + a short stereo reverb send per voice ("space")
  sfx       timed, panned, layered effects (each hit slightly varied so repeats never sound copied)
            + automatic whoosh/splat/page sounds on every transition in cues.json
  beds      ambience (rain, birds, crickets, room tone…) in decorrelated stereo
  music     v1 piano/strings score, widened, with a hall reverb, risers and hits on the beat grid
  ducking   music and beds dip smoothly under every spoken line (sidechain envelope follower)
  master    glue compression and a soft clip; finish.py then normalises to -14 LUFS, true peak -1 dB

  python3 v2/tools/mix.py --spec film.audio.json --voice work/<slug>/voice --cues work/<slug>/cues.json --out work/<slug>/mix.wav [--stems]

Extra spec keys (all optional, v1 keys still work):
  "sfx":  [[name, at, gain, {args…, "pan": -1..1, "verb": 0..1, "every": s, "until": s}], …]
  "beds": [[name, start, end, gain, {args}], …]
  "music": {"level": 0.06, "bpm": 72, "sections": [[start, end, chords, beats_per_chord, bpm, style, gain], …],
            "hits": [[t, "boom"|"riser"|"swell", gain]], "final_chord": true, "reverb": 0.28}
  "mix":   {"duck_db": 9, "bed_duck_db": 4, "auto_sfx": true, "transition_gain": 0.5, "dialogue": 1.0,
            "sfx": 0.8, "beds": 1.0, "music": 1.0}
New SFX in v2: whip splat page iris impact swish sub_boom flutter paper_fold plane_fly flap thump_soft riser2 swell
New beds in v2: roomtone wind   (plus v1: drone heartbeat rain birds crickets crackle breath)
"""
import argparse, json, os, sys
import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))   # v1 tools, used read-only
import sfxbase as M          # noqa: E402
import soundtrack as V1      # noqa: E402

SR = M.SR
T = M.t_axis
R = np.random.default_rng(2024)


# ------------------------------------------------------------------ dsp helpers
def fftconv(x, h):
    n = len(x) + len(h) - 1; N = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, N) * np.fft.rfft(h, N), N)[:n]


def make_ir(decay, pre=0.012, bright=0.6, seed=1):
    """Synthetic stereo room/hall impulse response (early reflections + damped diffuse tail)."""
    rg = np.random.default_rng(seed)
    n = int((decay * 1.2 + pre) * SR); t = np.arange(n) / SR
    out = []
    for ch in range(2):
        tail = rg.standard_normal(n) * np.exp(-6.9 * t / decay)
        # damping: darker as it decays
        k = np.clip(bright * np.exp(-t / (decay * 0.5)), 0.05, 1)
        y = np.zeros(n); acc = 0.0
        for i in range(n):  # one-pole low-pass with time-varying cutoff (cheap enough for IR sizes)
            acc += k[i] * (tail[i] - acc); y[i] = acc
        y[: int(pre * SR)] = 0
        for d, g in ((0.007, 0.5), (0.013, 0.35), (0.019, 0.28), (0.029, 0.2)):
            j = int((d + 0.002 * ch + pre * 0.5) * SR)
            if j < n: y[j] += g * (1 if (ch + int(d * 1000)) % 2 else -1)
        out.append(y / (np.sqrt(np.sum(y ** 2)) + 1e-9))
    return np.stack(out, 1)


IRS = {}
def ir(name):
    if name not in IRS:
        IRS[name] = {'studio': lambda: make_ir(0.32, 0.006, 0.7, 3), 'room': lambda: make_ir(0.6, 0.01, 0.55, 4),
                     'hall': lambda: make_ir(1.9, 0.022, 0.5, 5), 'plate': lambda: make_ir(1.2, 0.004, 0.8, 6)}[name]()
    return IRS[name]


def reverb(x, name, wet):
    """x mono or stereo → stereo wet signal (same length)."""
    h = ir(name)
    if x.ndim == 1: x = np.stack([x, x], 1)
    return np.stack([fftconv(x[:, c], h[:, c])[: len(x)] for c in range(2)], 1) * wet


def pan(x, p):
    p = float(np.clip(p, -1, 1)); a = (p + 1) * np.pi / 4
    return np.stack([x * np.cos(a), x * np.sin(a)], 1) * np.sqrt(2)   # centre = unity on both sides


def onepole(x, hz):
    a = np.exp(-2 * np.pi * hz / SR); y = np.zeros_like(x); acc = 0.0
    for i in range(len(x)): acc = a * acc + (1 - a) * x[i]; y[i] = acc
    return y


def follower(x, attack=0.025, release=0.45, hop=48):
    """Envelope follower (peak, attack/release) computed on a decimated signal, then upsampled."""
    xs = np.abs(x).reshape(-1)[: (len(x) // hop) * hop].reshape(-1, hop).max(1)
    aa, ar = np.exp(-hop / (attack * SR)), np.exp(-hop / (release * SR))
    e = np.zeros_like(xs); acc = 0.0
    for i, v in enumerate(xs):
        acc = aa * acc + (1 - aa) * v if v > acc else ar * acc + (1 - ar) * v
        e[i] = acc
    out = np.repeat(e, hop)
    return np.pad(out, (0, len(x) - len(out)), mode='edge')


def decorr(seed, n=480):
    """random-phase all-pass FIR (10 ms): same tone colour, different phase, so L and R decorrelate evenly"""
    rg = np.random.default_rng(100 + seed)
    ph = np.cumsum(rg.standard_normal(n // 2 + 1)) * 0.35; ph[0] = 0; ph[-1] = 0
    h = np.fft.irfft(np.exp(1j * ph), n)
    return h * np.hanning(n) / np.sqrt(np.sum((h * np.hanning(n)) ** 2) + 1e-12)


def resample(x, ratio):
    """Pitch/speed change by `ratio` (>1 = higher/shorter), linear interpolation (fine for SFX)."""
    if abs(ratio - 1) < 1e-4: return x
    n = int(len(x) / ratio); idx = np.arange(n) * ratio
    return np.interp(idx, np.arange(len(x)), x)


# ------------------------------------------------------------------ new v2 sounds
def s_whip(d=0.45):
    t = T(d); env = np.sin(np.pi * np.clip(t / d, 0, 1)) ** 3
    f = 400 + 3200 * np.sin(np.pi * t / d) ** 2
    air = M.bandpass(M.noise(d), 600, 9000)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.08
    return M.norm(M.lowpass_var(air, 1500, 8000) * env + tone * env)
def s_swish(d=0.35):
    t = T(d); return M.norm(M.bandpass(M.noise(d), 2000, 10000) * np.sin(np.pi * t / d) ** 2)
def s_splat():
    d = 0.7; t = T(d)
    body = M.bandpass(M.noise(d), 150, 2500) * np.exp(-t / 0.08)
    thump = np.sin(2 * np.pi * (90 - 40 * t) * t) * np.exp(-t / 0.09)
    drops = np.zeros(len(t))
    for i in range(7):
        j = int((0.05 + R.random() * 0.45) * SR); L = int(0.03 * SR)
        drops[j:j + L] += M.bandpass(R.standard_normal(L), 900, 5000)[: len(drops[j:j + L])] * np.exp(-np.arange(L) / (L / 4)) * (0.2 + 0.3 * R.random())
    return M.norm(body + 0.8 * thump + drops)
def s_page():
    d = 0.6; t = T(d)
    flutter = M.bandpass(M.noise(d), 1200, 8000) * (0.5 + 0.5 * np.abs(np.sin(2 * np.pi * 18 * t))) * np.sin(np.pi * t / d) ** 1.5
    snap = M.bandpass(M.noise(0.06), 800, 6000) * np.exp(-T(0.06) / 0.012)
    y = flutter.copy(); j = int(0.46 * SR); y[j:j + len(snap)] += snap * 1.2
    return M.norm(y)
def s_iris():
    d = 0.9; t = T(d)
    return M.norm(M.lowpass_var(M.noise(d), 300, 3000) * np.sin(np.pi * t / d) ** 2 * 0.6 + np.sin(2 * np.pi * (220 + 220 * t / d) * t) * np.sin(np.pi * t / d) * 0.15)
def s_sub_boom(d=2.0):
    t = T(d); return M.norm(np.sin(2 * np.pi * (55 - 18 * t / d) * t) * np.exp(-t / 0.6) * np.minimum(1, t / 0.005))
def s_impact():
    d = 1.2; t = T(d); n = len(t)
    fit = lambda x: np.pad(x, (0, max(0, n - len(x))))[:n]
    crack = M.bandpass(M.noise(0.12), 400, 8000) * np.exp(-T(0.12) / 0.03)
    return M.norm(fit(V1.thud()) * 0.9 + fit(s_sub_boom(d)) * 0.8 + fit(crack) * 0.6)
def s_flutter(d=1.0):
    t = T(d); return M.norm(M.bandpass(M.noise(d), 700, 5000) * (0.4 + 0.6 * np.abs(np.sin(2 * np.pi * 11 * t))) * np.sin(np.pi * t / d))
def s_paper_fold():
    d = 0.5; t = T(d)
    crease = M.bandpass(M.noise(d), 1500, 9000) * np.exp(-((t - 0.32) / 0.04) ** 2)
    slide = M.bandpass(M.noise(d), 500, 4000) * np.sin(np.pi * np.clip(t / 0.3, 0, 1)) * 0.5
    return M.norm(slide + crease * 1.3)
def s_plane_fly(d=1.6):
    t = T(d); air = M.lowpass_var(M.bandpass(M.noise(d), 300, 6000), 2500, 900)
    return M.norm(air * np.sin(np.pi * t / d) ** 1.2 * (1 + 0.25 * np.sin(2 * np.pi * 3 * t)))
def s_flap():
    d = 0.18; t = T(d); return M.norm(M.bandpass(M.noise(d), 400, 3000) * np.exp(-t / 0.04))
def s_thump_soft():
    t = T(0.4); return M.norm(np.sin(2 * np.pi * (110 - 50 * t) * t) * np.exp(-t / 0.07) + M.bandpass(M.noise(0.4), 200, 1500) * np.exp(-t / 0.03) * 0.4)
def s_riser(d=2.0):
    t = T(d); f = 180 + 900 * (t / d) ** 2.2
    tone = sum(np.sin(2 * np.pi * np.cumsum(f * m) / SR) / m for m in (1, 1.5, 2))
    return M.norm((tone * 0.4 + M.bandpass(M.noise(d), 1500, 10000) * 0.5) * (t / d) ** 2.4)
def s_swell(d=2.5):
    t = T(d); fs = [V1.midi(n) for n in (48, 55, 60, 64, 67)]
    return M.norm(sum(np.sin(2 * np.pi * f * t) for f in fs) * (t / d) ** 2 * np.minimum(1, (d - t) / 0.08))


SFX = dict(V1.SFX)
SFX.update({'whip': s_whip, 'swish': s_swish, 'splat': s_splat, 'page': s_page, 'iris': s_iris, 'sub_boom': s_sub_boom,
            'impact': s_impact, 'flutter': s_flutter, 'paper_fold': s_paper_fold, 'plane_fly': s_plane_fly, 'flap': s_flap,
            'thump_soft': s_thump_soft, 'riser2': s_riser, 'swell': s_swell})
SFX_D = {'scribble': 1.0, 'swoop': 1.0}
def b_roomtone(d):
    """quiet room: low pink-ish rumble + faint air, like a real recording space"""
    x = M.noise(d); lo = onepole(x, 180) * 3.0; air = (x - onepole(x, 3000)) * 0.08
    return M.norm(lo + air) * 0.6
def b_wind(d):
    """outdoor breeze: band-limited noise with slow gusts"""
    x = M.noise(d); t = T(d)
    gust = 0.55 + 0.45 * np.sin(2 * np.pi * 0.11 * t + 1.3) * np.sin(2 * np.pi * 0.047 * t + 0.4)
    y = onepole(x, 900) - onepole(x, 120)
    return M.norm(y * gust)
BEDS = dict(V1.BEDS); BEDS.update({'roomtone': b_roomtone, 'wind': b_wind})
HITS = {'boom': s_sub_boom, 'riser': s_riser, 'swell': s_swell, 'impact': s_impact}


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True); ap.add_argument("--voice", required=True)
    ap.add_argument("--cues", default=None); ap.add_argument("--out", required=True); ap.add_argument("--stems", action="store_true")
    a = ap.parse_args()
    spec = json.load(open(a.spec, encoding="utf-8"))
    mx = dict({"duck_db": 9, "bed_duck_db": 4, "auto_sfx": True, "transition_gain": 0.45,
               "dialogue": 1.0, "sfx": 0.8, "beds": 1.0, "music": 1.0}, **spec.get("mix", {}))
    total = float(spec["duration"]); n = int(total * SR)
    st = lambda: np.zeros((n, 2))

    def put(bus, sig, at):
        j = int(round(at * SR))
        if j >= n or j + len(sig) <= 0: return
        if j < 0: sig = sig[-j:]; j = 0
        L = min(len(sig), n - j); bus[j:j + L] += sig[:L]

    # ---- dialogue
    timing = json.load(open(os.path.join(a.voice, "timing.json")))
    dry, wet = st(), st()
    sends = {}
    for ln in timing["lines"]:
        cfg = spec["voices"][ln["speaker"]]
        x, _ = sf.read(os.path.join(a.voice, ln["file"]))
        x = x * cfg.get("gain", 0.9)
        put(dry, pan(x, cfg.get("pan", 0)), ln["start"])
        space = cfg.get("space", "studio")
        if space != "none":
            sends.setdefault(space, np.zeros(n)); j = int(ln["start"] * SR); L = min(len(x), n - j); sends[space][j:j + L] += x[:L]
    for space, sig in sends.items():
        wet += reverb(sig, space, {'studio': 0.10, 'room': 0.16, 'hall': 0.22, 'plate': 0.14}[space])
    dialogue = dry + wet

    # ---- sfx
    sfx, sfx_send = st(), np.zeros(n)
    events = list(spec.get("sfx", []))
    if a.cues and os.path.exists(a.cues) and mx["auto_sfx"]:
        cues = json.load(open(a.cues))
        for c in cues.get("cues", []):
            if c.get("kind") == "transition" and c.get("sfx"):
                name = c["sfx"]; dur = c.get("dur", 0.5)
                at = c["at"] - (dur / 2 if name in ("whip", "swish", "iris", "page") else 0.0)
                if name == "splat": at = c["at"] - dur / 2 + 0.02
                args = {"pan": 0.0}
                if name == "whip": args["d"] = max(0.3, dur)
                events.append([name, at, mx["transition_gain"], args])
                if name == "impact": events.append(["sub_boom", c["at"], mx["transition_gain"] * 0.7, {}])
            if c.get("kind") == "sfx":
                events.append([c["name"], c["at"], c.get("gain", 0.4), {k: v for k, v in c.items() if k in ("pan", "d", "note", "verb")}])
    for e in events:
        name, at, g = e[0], float(e[1]), float(e[2]); args = dict(e[3]) if len(e) > 3 else {}
        every, until = args.pop("every", None), args.pop("until", None)
        pn, vb = args.pop("pan", 0.0), args.pop("verb", 0.12)
        vary = args.pop("vary", 0.04)
        if name in SFX_D and 'd' not in args: args['d'] = SFX_D[name]
        times = [at] if not every else list(np.arange(at, until, every))
        for k, t0 in enumerate(times):
            sig = SFX[name](**args)
            r = 1 + vary * (R.random() * 2 - 1)            # each hit slightly different (no machine-gun repeats)
            sig = resample(sig, r) * (1 + 0.12 * (R.random() * 2 - 1)) * g
            put(sfx, pan(sig, pn + (R.random() - 0.5) * 0.08 if every else pn), t0)
            j = int(t0 * SR); L = min(len(sig), n - j)
            if 0 <= j < n: sfx_send[j:j + L] += sig[:L] * vb
    sfx += reverb(sfx_send, 'room', 1.0)

    # ---- beds (decorrelated stereo: each side generated separately)
    beds = st()
    for e in spec.get("beds", []):
        name, a0, a1, g = e[0], float(e[1]), float(e[2]), float(e[3]); args = e[4] if len(e) > 4 else {}
        d = a1 - a0
        L_ = BEDS[name](d, **args); R_ = BEDS[name](d, **args)
        m = min(len(L_), len(R_)); sig = np.stack([L_[:m] * 0.8 + R_[:m] * 0.2, R_[:m] * 0.8 + L_[:m] * 0.2], 1)
        tt = np.arange(m) / SR; fd = min(1.5, d / 3)
        sig *= np.minimum(1, np.minimum(tt / fd, (m / SR - tt) / fd))[:, None] * g
        put(beds, sig, a0)

    # ---- music: v1 score → widened stereo + hall + hits
    music = st()
    if spec.get("music"):
        m = spec["music"]
        mono = V1.score(total, m["sections"], m.get("final_chord", True))
        mono = mono / (np.sqrt(np.mean(mono ** 2)) + 1e-9) * m.get("level", 0.06)
        mono = np.pad(mono, (0, max(0, n - len(mono))))[:n]
        # balanced widening: each side gets its own flat-magnitude decorrelation filter (no lopsided Haas trick)
        stereo = np.stack([0.62 * mono + 0.38 * fftconv(mono, decorr(1))[:n], 0.62 * mono + 0.38 * fftconv(mono, decorr(2))[:n]], 1)
        hp = mono - onepole(mono, 160)                                           # keep the hall out of the low end
        music = stereo + reverb(hp, 'hall', m.get("reverb", 0.28))
        for h in m.get("hits", []):
            t0, kind, g = float(h[0]), h[1], float(h[2]) if len(h) > 2 else 0.4
            sig = HITS[kind]()
            if kind in ("riser", "swell"): t0 -= len(sig) / SR          # risers END on the hit time
            put(music, pan(sig, 0) * g, t0)

    # ---- ducking: music and beds dip under the voice
    env = follower(dry.mean(1), attack=0.03, release=0.5)
    vk = np.clip(env / 0.06, 0, 1)
    duck = 10 ** (-mx["duck_db"] * vk / 20); bduck = 10 ** (-mx["bed_duck_db"] * vk / 20)
    music *= duck[:, None]; beds *= bduck[:, None]

    stems = {"dialogue": dialogue * mx["dialogue"], "sfx": sfx * mx["sfx"], "beds": beds * mx["beds"], "music": music * mx["music"]}
    mix = sum(stems.values())

    # ---- master: glue compression (RMS follower, 2:1 above -18 dBFS) + soft clip
    mix = mix / (np.sqrt(np.mean(mix ** 2)) + 1e-9) * 0.1          # about -20 dBFS RMS
    rms = np.sqrt(np.maximum(1e-12, follower(mix.mean(1) ** 2, 0.01, 0.25)))
    thr = 10 ** (-18 / 20)
    gain = np.where(rms > thr, (rms / thr) ** -0.5, 1.0)
    out = mix * gain[:, None]
    out = np.tanh(out * 1.6) / 1.6
    out *= 0.9 / (np.max(np.abs(out)) + 1e-9)
    sf.write(a.out, out.astype(np.float32), SR, subtype="FLOAT")
    if a.stems:
        sd = os.path.splitext(a.out)[0] + "_stems"; os.makedirs(sd, exist_ok=True)
        for k, v in stems.items(): sf.write(os.path.join(sd, k + ".wav"), (v / (np.max(np.abs(mix)) + 1e-9) * 0.9).astype(np.float32), SR, subtype="FLOAT")
    print(f"mix → {a.out}  ({total:.1f}s stereo {SR} Hz; {len(events)} sfx events; ducking {mx['duck_db']} dB)")


if __name__ == "__main__":
    main()
