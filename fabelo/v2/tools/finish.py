#!/usr/bin/env python3
"""
Fabelo Studio v2: finishing (the "online edit"). Turns the master video and the mix into the delivery file.

Picture:  paper texture (static, like real paper)  →  colour grade  →  soft vignette  →  fine film grain
          →  high-bitrate H.264 (x264 slow, crf 15, tune animation), optional upscale to 4K.
Sound:    two-pass loudness normalisation to -14 LUFS integrated, true peak -1 dBTP (YouTube's target),
          AAC 320 kb/s 48 kHz.  Then the final file is measured again and a report is written.

  python3 v2/tools/finish.py --video work/<slug>/master.mp4 --audio work/<slug>/mix.wav --out work/<slug>/final.mp4
         [--grade warm|neutral|cool|none] [--paper 0.07] [--grain 0.3] [--vignette 0.3] [--crf 15]
         [--size 2160x3840] [--report work/<slug>/report.json]

Strengths are 0..1. Keep them low: the look must stay Scribble's clean ink on warm paper.
"""
import argparse, json, os, re, subprocess, sys, tempfile
import numpy as np

GRADES = {
    # Brand-safe grades: a gentle contrast curve and at most a whisper of midtone warmth.
    # They keep ink #1B1B1B, scarf #E63946 and paper #FBF7EE within a few RGB steps (qc checks this).
    "warm": "curves=all='0/0 0.1/0.092 0.5/0.5 0.9/0.905 1/1',colorbalance=rm=0.012:bm=-0.012:pl=1",
    "neutral": "curves=all='0/0 0.1/0.092 0.5/0.5 0.9/0.905 1/1'",
    "cool": "curves=all='0/0 0.1/0.092 0.5/0.5 0.9/0.905 1/1',colorbalance=rm=-0.01:bm=0.014:pl=1",
    "none": "null",
}


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration,bit_rate,size:stream=codec_type,width,height,r_frame_rate,sample_rate,channels,codec_name",
                          "-of", "json", path], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def paper_texture(w, h, path, seed=7):
    """Grey-centred paper: soft mottling + fine fibres. Used with soft-light blend, so 50% grey = no change."""
    rng = np.random.default_rng(seed)
    sw, sh = max(2, w // 24), max(2, h // 24)
    mott = rng.standard_normal((sh, sw)).astype(np.float32)
    # upscale the mottling smoothly (separable linear interpolation)
    ys, xs = np.linspace(0, sh - 1, h), np.linspace(0, sw - 1, w)
    m = np.array([np.interp(xs, np.arange(sw), row) for row in mott])
    m = np.array([np.interp(ys, np.arange(sh), col) for col in m.T]).T
    fib = rng.standard_normal((h, w)).astype(np.float32)
    k = np.ones(5, np.float32) / 5           # streak the grain sideways a little, like paper fibres
    fib = np.apply_along_axis(lambda r: np.convolve(r, k, mode="same"), 1, fib)
    tex = 0.6 * m / (np.abs(m).max() + 1e-6) + 0.4 * fib / (np.abs(fib).max() + 1e-6)
    img = np.clip(128 + 60 * tex, 0, 255).astype(np.uint8)
    with open(path, "wb") as f:              # binary PGM, readable by ffmpeg, no extra libraries
        f.write(f"P5 {w} {h} 255\n".encode()); f.write(img.tobytes())


def vignette_mask(w, h, strength, path):
    """Soft oval vignette: 1.0 over most of the frame, only the outer edge darkens (max 14% at the corners)."""
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((x - w / 2) / (w / 2)) ** 2 + ((y - h / 2) / (h / 2)) ** 2) / np.sqrt(2)
    k = np.clip((r - 0.45) / 0.55, 0, 1)
    img = np.clip(255 * (1 - 0.14 * min(1, strength) * k ** 2.2), 0, 255).astype(np.uint8)
    with open(path, "wb") as f:
        f.write(f"P5 {w} {h} 255\n".encode()); f.write(img.tobytes())


def loudnorm_measure(audio, pre):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", audio, "-af", pre + "loudnorm=I=-14:TP=-1:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True, check=True)
    js = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    if not js: raise SystemExit("loudnorm: could not read the measurement")
    return json.loads(js.group(0))


def measure_final(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    s = r.stderr[r.stderr.rfind("Summary:"):]
    get = lambda pat: (lambda m: float(m.group(1)) if m else None)(re.search(pat, s))
    return {"integrated_lufs": get(r"I:\s+(-?[\d.]+) LUFS"), "lra_lu": get(r"LRA:\s+(-?[\d.]+) LU"), "true_peak_dbtp": get(r"Peak:\s+(-?[\d.]+) dBFS")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True); ap.add_argument("--audio"); ap.add_argument("--out", required=True)
    ap.add_argument("--grade", default="warm", choices=list(GRADES))
    ap.add_argument("--paper", type=float, default=0.07); ap.add_argument("--grain", type=float, default=0.3)
    ap.add_argument("--vignette", type=float, default=0.3); ap.add_argument("--crf", type=float, default=15)
    ap.add_argument("--size", help="output size WxH, e.g. 2160x3840 for 4K vertical"); ap.add_argument("--report")
    ap.add_argument("--preset", default="slow")
    a = ap.parse_args()

    info = probe(a.video)
    vs = next(s for s in info["streams"] if s["codec_type"] == "video")
    W, H = vs["width"], vs["height"]
    dur = float(info["format"]["duration"])
    OW, OH = (map(int, a.size.lower().split("x")) if a.size else (W, H))
    tmp = tempfile.mkdtemp()

    # ---------- picture chain
    inputs = ["-i", a.video]
    fc = "[0:v]format=gbrp[v0];"
    cur = "v0"
    if a.paper > 0:
        tex = os.path.join(tmp, "paper.pgm"); paper_texture(W, H, tex)
        inputs += ["-loop", "1", "-framerate", vs["r_frame_rate"], "-i", tex]
        fc += f"[1:v]format=gray,format=gbrp,trim=duration={dur:.3f}[pp];[{cur}][pp]blend=all_mode=softlight:all_opacity={min(1, a.paper):.3f}:shortest=1[v1];"
        cur = "v1"
    if a.vignette > 0:
        vg = os.path.join(tmp, "vig.pgm"); vignette_mask(W, H, a.vignette, vg)
        n = len([x for x in inputs if x == "-i"])
        inputs += ["-loop", "1", "-framerate", vs["r_frame_rate"], "-i", vg]
        fc += f"[{n}:v]format=gray,format=gbrp,trim=duration={dur:.3f}[vg];[{cur}][vg]blend=all_mode=multiply:shortest=1[v2];"
        cur = "v2"
    chain = [GRADES[a.grade]]
    if a.grain > 0: chain.append(f"noise=c0s={3 + 9 * min(1, a.grain):.1f}:c0f=t+u")   # grain on all channels in RGB, mean-neutral
    # one explicit RGB → BT.709 conversion (the file is tagged 709, so colours decode exactly)
    chain.append(f"scale={OW}:{OH}:flags=lanczos:out_color_matrix=bt709:out_range=tv")
    chain.append("format=yuv420p")
    fc += f"[{cur}]{','.join(chain)}[vout]"

    cmd = ["ffmpeg", "-y", "-v", "error", "-stats"] + inputs
    amap = []
    if a.audio:
        # ---------- sound: fades + two-pass loudnorm (linear) to -14 LUFS / -1 dBTP
        pre = f"apad,atrim=0:{dur:.3f},afade=t=in:d=0.02,afade=t=out:st={max(0, dur - 0.6):.3f}:d=0.6,"
        m = loudnorm_measure(a.audio, pre)
        ln = (f"loudnorm=I=-14:TP=-1:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
              f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true:print_format=summary")
        cmd += ["-i", a.audio]
        ai = len([x for x in inputs if x == "-i"])
        fc += f";[{ai}:a]{pre}{ln},aresample=48000[aout]"
        amap = ["-map", "[aout]", "-c:a", "aac", "-b:a", "320k", "-ar", "48000"]
    cmd += ["-filter_complex", fc, "-map", "[vout]"] + amap + [
        "-c:v", "libx264", "-preset", a.preset, "-crf", str(a.crf), "-tune", "animation", "-profile:v", "high",
        "-x264-params", "aq-mode=3:deblock=-1,-1", "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709",
        "-colorspace", "bt709", "-movflags", "+faststart", "-t", f"{dur:.3f}", a.out]
    print("finishing →", a.out)
    run(cmd)

    # ---------- report
    fin = probe(a.out)
    fv = next(s for s in fin["streams"] if s["codec_type"] == "video")
    rep = {"file": os.path.basename(a.out), "duration_s": round(float(fin["format"]["duration"]), 2),
           "size": f"{fv['width']}x{fv['height']}", "fps": fv["r_frame_rate"],
           "video_mbps": round(int(fin["format"]["bit_rate"]) / 1e6, 1), "file_mb": round(int(fin["format"]["size"]) / 1e6, 1),
           "grade": a.grade, "paper": a.paper, "grain": a.grain, "vignette": a.vignette}
    if a.audio:
        rep["audio"] = measure_final(a.out)
        lu, tp = rep["audio"]["integrated_lufs"], rep["audio"]["true_peak_dbtp"]
        rep["audio_ok"] = bool(lu is not None and abs(lu + 14) <= 1.0 and tp is not None and tp <= -0.9)
    print(json.dumps(rep, indent=1))
    if a.report: json.dump(rep, open(a.report, "w"), indent=1)


if __name__ == "__main__":
    main()
