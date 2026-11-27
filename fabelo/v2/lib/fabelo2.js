/*!
 * Fabelo Studio v2 — pro film layer on top of the v1 Scribble engine.
 *
 * Load AFTER ../../lib/scribble.js (v1, used read-only). Scribble himself is still drawn ONLY
 * by scribble.js, so his look never changes. This file adds what a professional edit needs:
 *
 *   - shots and cuts (each shot has its own staging, camera and timing)
 *   - an aspect-aware camera: frame a box and it stays fully visible at 16:9, 9:16 and 1:1,
 *     push-in, pan, follow, handheld drift, shake, dutch angle
 *   - parallax layers with depth (and soft depth-of-field blur for foreground)
 *   - pro character motion: spring overshoot and settle, follow-through on forearms and head,
 *     anticipation, idle breathing, scarf drag and swing
 *   - a transition library: cut, dissolve, dip, whip pan, iris, ink splash, page turn,
 *     match cut, smash cut
 *   - screen-space titles and word-by-word Shorts captions synced to the real voice timing
 *   - cues (cuts, transitions, beats) that the audio mixer reads to place whooshes on the cut
 *
 * Everything is a pure function of time t, so record.js / record2.js can seek any frame.
 * Coordinates: the safe square [-500, 500] is visible on every ratio (same as v1).
 */
(function (global) {
  'use strict';
  const S = global.Scribble;
  if (!S) throw new Error('fabelo2.js needs lib/scribble.js loaded first');
  const C = S.palette, sv = S.svg;

  /* ------------------------------------------------------------------ math */
  const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
  const lerp = (a, b, k) => a + (b - a) * k;
  const f = (n) => Math.round(n * 100) / 100;
  // Precise number for anything that moves the whole picture (camera, zoom, root fade).
  // f()'s 0.01 steps are fine for drawing, but on a scale they snap a slow push-in into
  // visible 1 % jumps (about 10 px at the frame edge on a 1080p frame), which reads as a shaky zoom.
  const fp = (n) => { const r = Math.round(n * 1e5) / 1e5; return Object.is(r, -0) ? 0 : r; };
  const TAU = Math.PI * 2;
  // deterministic smooth noise in [-1, 1]
  const hash = (n) => { const s = Math.sin(n * 127.1 + 311.7) * 43758.5453; return (s - Math.floor(s)) * 2 - 1; };
  const vnoise = (x, seed = 0) => {
    const i = Math.floor(x), fr = x - i, u = fr * fr * (3 - 2 * fr);
    return lerp(hash(i + seed * 57.3), hash(i + 1 + seed * 57.3), u);
  };
  const fbm = (x, seed = 0) => vnoise(x, seed) * 0.62 + vnoise(x * 2.07, seed + 3) * 0.28 + vnoise(x * 4.11, seed + 7) * 0.1;
  // camera drift noise: quintic fade, so speed AND acceleration are continuous (no micro-jolts),
  // and only the two low octaves, so handheld reads as a slow breath, never as a tremble
  const qnoise = (x, seed = 0) => {
    const i = Math.floor(x), fr = x - i, u = fr * fr * fr * (fr * (fr * 6 - 15) + 10);
    return lerp(hash(i + seed * 57.3), hash(i + 1 + seed * 57.3), u);
  };
  const drift = (x, seed = 0) => qnoise(x, seed) * 0.72 + qnoise(x * 1.93, seed + 3) * 0.28;

  /* ---------------------------------------------------------- pro easings */
  // Added to Scribble.EASE so every v1 track (moveTo, scaleTo, rotateTo) can use them too.
  const EX = {
    sineInOut: (k) => -(Math.cos(Math.PI * k) - 1) / 2,
    quintOut: (k) => 1 - Math.pow(1 - k, 5),
    quintInOut: (k) => (k < 0.5 ? 16 * k ** 5 : 1 - Math.pow(-2 * k + 2, 5) / 2),
    expoOut: (k) => (k >= 1 ? 1 : 1 - Math.pow(2, -10 * k)),
    expoIn: (k) => (k <= 0 ? 0 : Math.pow(2, 10 * k - 10)),
    expoInOut: (k) => (k <= 0 ? 0 : k >= 1 ? 1 : k < 0.5 ? Math.pow(2, 20 * k - 10) / 2 : (2 - Math.pow(2, -20 * k + 10)) / 2),
    smooth: (k) => k * k * k * (k * (k * 6 - 15) + 10),            // smootherstep
    backOut: (k) => { const c = 1.25; return 1 + (c + 1) * Math.pow(k - 1, 3) + c * Math.pow(k - 1, 2); }, // soft overshoot
    backIn: (k) => { const c = 1.25; return (c + 1) * k * k * k - c * k * k; },
    settle: (k) => (k >= 1 ? 1 : 1 - Math.exp(-6 * k) * Math.cos(9 * k)),  // overshoot + settle
    snap: (k) => (k >= 1 ? 1 : 1 - Math.pow(1 - k, 4) * (1 + 0 * k))
  };
  for (const k in EX) if (!S.EASE[k]) S.EASE[k] = EX[k];
  const E = S.EASE;
  const ease = (name) => (typeof name === 'function' ? name : E[name] || E.inOut);

  // damped-spring step response; x = time / duration, crossing 1 near x = xc
  function spring(x, zeta, xc = 0.75) {
    if (x <= 0) return 0;
    const wdN = Math.sqrt(1 - zeta * zeta);
    const w = (Math.PI - Math.atan(wdN / zeta)) / (xc * wdN), wd = w * wdN;
    return 1 - Math.exp(-zeta * w * x) * (Math.cos(wd * x) + (zeta / wdN) * Math.sin(wd * x));
  }

  /* ------------------------------------------------------------- tracks */
  class Track {
    constructor(v) { this.v0 = v; this.segs = []; }
    to(t0, dur, value, e = 'inOut') { this.segs.push({ t0, t1: t0 + Math.max(0, dur), to: value, e: ease(e) }); this.segs.sort((a, b) => a.t0 - b.t0); return this; }
    at(t) {
      // The latest move that has started wins, and it starts from the value the track has at
      // that moment. (A move added on top of one still running used to be ignored until the
      // first ended and then jump, which showed up as a snap in an overlapping push / frame.)
      let v = this.v0;
      for (let i = 0; i < this.segs.length; i++) {
        const s = this.segs[i];
        if (t < s.t0) break;
        const nxt = this.segs[i + 1];
        const from = this._from(i);
        if (nxt && nxt.t0 <= t) { v = from; continue; }
        if (t >= s.t1) return s.to;
        return lerp(from, s.to, s.e((t - s.t0) / (s.t1 - s.t0 || 1)));
      }
      return v;
    }
    _from(i) {
      if (!this._cache || this._cache.n !== this.segs.length || this._cache.v0 !== this.v0) this._cache = { n: this.segs.length, v0: this.v0, v: [] };
      const c = this._cache.v;
      if (c[i] === undefined) c[i] = i === 0 ? this.v0 : this.at(this.segs[i].t0 - 1e-9);
      return c[i];
    }
  }

  /* ------------------------------------------------------- pro motion */
  const LIMB = {           // zeta (lower = more overshoot), lag (s) = follow-through, cap (deg)
    lean: { z: 0.72, lag: 0.0, cap: 5 },
    head: { z: 0.5, lag: 0.035, cap: 7 },
    up: { z: 0.6, lag: 0.0, cap: 9 },
    fore: { z: 0.46, lag: 0.07, cap: 14 }
  };
  const windowW = (t, t0, t1, r) => clamp(Math.min((t - t0) / r, (t1 - t) / r));
  const clonePose = (p) => ({ lean: p.lean || 0, head: p.head || 0, jump: p.jump || 0, aL: [p.aL[0], p.aL[1]], aR: [p.aR[0], p.aR[1]], lL: [p.lL[0], p.lL[1]], lR: [p.lR[0], p.lR[1]] });

  /**
   * Upgrade a v1 character with professional secondary motion. Scribble's drawing is untouched:
   * only the pose angles fed to scribble.js get overshoot, lag and breathing.
   * opts: { overshoot: 1, followThrough: 1, breathe: 1, anticipation: 1, scarf: 1 }  (0 turns one off)
   */
  function enhance(ch, opts = {}) {
    const o = Object.assign({ overshoot: 1, followThrough: 1, breathe: 1, anticipation: 1, scarf: 1 }, opts);
    const orig = ch.stateAt.bind(ch);
    const seed = ch.seed * 3.1 + 0.7;
    const keyDur = (k) => Math.max(0.22, k.dur);

    function walkW(t) {
      let w = 0;
      for (const wk of ch.walks) w = Math.max(w, windowW(t, wk.t0 - 0.05, wk.t1 + 0.2, 0.2));
      return w;
    }
    // eased reference (what v1 computes) vs spring version, per field
    function delta(t) {
      let pe = clonePose(ch.initPose), ps = clonePose(ch.initPose);
      let antic = null;
      for (const k of ch.poseKeys) {
        const kp = k.pose;
        if (t < k.t) {
          // anticipation: small counter-move in the 0.14 s before a big change
          if (o.anticipation && k.t - t < 0.16 && !antic) antic = { k, w: Math.sin(Math.PI * clamp((t - (k.t - 0.16)) / 0.16)), from: { lean: pe.lean, aL: pe.aL.slice(), aR: pe.aR.slice() } };
          break;
        }
        const d = keyDur(k), ke = k.dur <= 0 ? 1 : E.inOut(clamp((t - k.t) / k.dur));
        const sp = (L) => {
          const x = (t - k.t - L.lag * o.followThrough) / d;
          return lerp(ke, spring(x, L.z), o.overshoot);
        };
        const kl = sp(LIMB.lean), kh = sp(LIMB.head), ku = sp(LIMB.up), kf = sp(LIMB.fore);
        pe = { lean: lerp(pe.lean, kp.lean || 0, ke), head: lerp(pe.head, kp.head || 0, ke), aL: [lerp(pe.aL[0], kp.aL[0], ke), lerp(pe.aL[1], kp.aL[1], ke)], aR: [lerp(pe.aR[0], kp.aR[0], ke), lerp(pe.aR[1], kp.aR[1], ke)] };
        ps = { lean: lerp(ps.lean, kp.lean || 0, kl), head: lerp(ps.head, kp.head || 0, kh), aL: [lerp(ps.aL[0], kp.aL[0], ku), lerp(ps.aL[1], kp.aL[1], kf)], aR: [lerp(ps.aR[0], kp.aR[0], ku), lerp(ps.aR[1], kp.aR[1], kf)] };
      }
      const cap = (v, L) => clamp(v, -L.cap, L.cap);
      const out = {
        lean: cap(ps.lean - pe.lean, LIMB.lean), head: cap(ps.head - pe.head, LIMB.head),
        aL: [cap(ps.aL[0] - pe.aL[0], LIMB.up), cap(ps.aL[1] - pe.aL[1], LIMB.fore)],
        aR: [cap(ps.aR[0] - pe.aR[0], LIMB.up), cap(ps.aR[1] - pe.aR[1], LIMB.fore)]
      };
      if (antic && antic.w > 0) {
        const kp = antic.k.pose, fr = antic.from, a = 0.1 * antic.w * o.anticipation;
        out.lean -= clamp((kp.lean || 0) - fr.lean, -30, 30) * a;
        out.aL[0] -= clamp(kp.aL[0] - fr.aL[0], -60, 60) * a; out.aR[0] -= clamp(kp.aR[0] - fr.aR[0], -60, 60) * a;
      }
      return out;
    }
    const vx = (t) => (ch.x.at(t) - ch.x.at(t - 0.06)) / 0.06;
    function scarfDyn(t, facing, ww) {
      // impulse response of the scarf to changes in body speed: lags when starting, swings when stopping
      let s = 0; const h = 1 / 30;
      for (let i = 0; i < 36; i++) {
        const tau = i * h, dv = (vx(t - tau) - vx(t - tau - h)) * facing;
        if (dv) s += -0.05 * dv * Math.exp(-tau / 0.38) * Math.cos(TAU * tau / 0.62);
      }
      s += -0.03 * vx(t) * facing * (1 - ww);  // steady drag on slides (walks already have it in v1)
      return clamp(s, -14, 14);
    }

    ch.stateAt = function (t) {
      const st = orig(t);
      const ww = walkW(t), k = 1 - ww;
      if (k > 0 && (o.overshoot || o.followThrough || o.anticipation)) {
        const d = delta(t), p = st.pose;
        p.lean += d.lean * k; p.head += d.head * k;
        p.aL[0] += d.aL[0] * k; p.aL[1] += d.aL[1] * k; p.aR[0] += d.aR[0] * k; p.aR[1] += d.aR[1] * k;
      }
      if (o.breathe && k > 0) {
        const b = Math.sin(TAU * t / 3.8 + seed), b2 = Math.sin(TAU * t / 5.3 + seed * 2);
        const p = st.pose, br = o.breathe * k;
        p.lean += 0.7 * b * br; p.head += 1.1 * b2 * br;
        p.aL[0] -= 1.6 * b * br; p.aR[0] += 1.6 * b * br; p.aL[1] -= 1.2 * b2 * br; p.aR[1] += 1.2 * b2 * br;
      }
      if (o.scarf) st.scarfSway = (st.scarfSway || 0) + scarfDyn(t, st.facing, ww) * o.scarf;
      return st;
    };
    ch.motion = o;
    return ch;
  }

  /* --------------------------------------------------------------- camera */
  // Camera moves use easings whose acceleration is continuous too (not only the speed). A plain
  // cubic / quint in-out flips its acceleration in one frame at the midpoint, which shows as a small
  // lurch on a big zoom. Named in-out easings are swapped for smooth ones of similar steepness.
  const camEase = (e) => {
    if (typeof e !== 'string') return e;
    if (e === 'inOut' || e === 'cubicInOut' || e === 'quadInOut') return E.smooth;
    if (e === 'quintInOut' || e === 'expoInOut') return (k) => E.smooth(E.smooth(k));
    return e;
  };
  class Camera {
    constructor(shot) {
      this.shot = shot;
      this.cx = new Track(0); this.cy = new Track(0);
      this.lw = new Track(Math.log(1000)); this.lh = new Track(Math.log(1000));
      this.rot = new Track(0);
      this.shakes = []; this.follows = [];
      this.hand = 0; this.minZoom = 0.75;
    }
    /** Initial framing. box = [cx, cy, w, h] in world units (the box is kept fully visible on every ratio). */
    set(box) { this.cx.v0 = box[0]; this.cy.v0 = box[1]; this.lw.v0 = Math.log(box[2]); this.lh.v0 = Math.log(box[3] || box[2]); return this; }
    /** Move / zoom the framing to `box` between at and at+dur. */
    frame(at, dur, box, e = 'inOut') {
      e = camEase(e);
      this.cx.to(at, dur, box[0], e); this.cy.to(at, dur, box[1], e);
      this.lw.to(at, dur, Math.log(box[2]), e); this.lh.to(at, dur, Math.log(box[3] || box[2]), e);
      return this;
    }
    /** Slow push-in on a point: zoom factor `amount` (1.15 = 15 % closer) over [at, at+dur]. */
    push(at, dur, amount = 1.15, center = null, e = 'sineInOut') {
      const w = Math.exp(this.lw.at(at)), h = Math.exp(this.lh.at(at));
      const c = center || [this.cx.at(at), this.cy.at(at)];
      return this.frame(at, dur, [c[0], c[1], w / amount, h / amount], e);
    }
    /** Follow a character's x (with lag) between t0 and t1. */
    follow(t0, t1, ch, o = {}) { this.follows.push(Object.assign({ t0, t1, ch, dx: 0, lag: 0.3, ramp: 0.5 }, o)); return this; }
    /** Dutch angle (degrees). */
    tilt(at, dur, deg, e = 'inOut') { this.rot.to(at, dur, deg, camEase(e)); return this; }
    /** Camera shake (impacts, smash cuts). amp in world units. */
    shake(at, dur = 0.4, amp = 14) { this.shakes.push({ at, dur, amp }); return this; }
    /** Subtle handheld drift for the whole shot (0 = locked tripod, 1 = gentle, 2 = nervous). */
    handheld(amount = 1) { this.hand = amount; return this; }

    /** Camera state for viewport v (viewBox w/h). */
    at(t, v) {
      let cx = this.cx.at(t), cy = this.cy.at(t);
      const bw = Math.exp(this.lw.at(t)), bh = Math.exp(this.lh.at(t));
      for (const fo of this.follows) {
        const w = windowW(t, fo.t0, fo.t1, fo.ramp);
        if (w > 0) cx = lerp(cx, fo.ch.x.at(t - fo.lag) + fo.dx, E.inOut(w));
      }
      let z = Math.min(v.w / bw, v.h / bh);
      z = Math.max(this.minZoom, z);
      let rot = this.rot.at(t);
      const sd = this.shot.seed;
      if (this.hand) {
        // calmer while the framing zooms, so a push-in stays a clean glide instead of a wobble
        const zr = Math.abs(this.lw.at(t + 0.05) - this.lw.at(t - 0.05)) / 0.1;
        const a = this.hand / (1 + zr * 25);
        cx += drift(t * 0.35, sd) * 6 * a / z; cy += drift(t * 0.3, sd + 11) * 4 * a / z; rot += drift(t * 0.25, sd + 23) * 0.25 * a;
      }
      for (const s of this.shakes) {
        const k = (t - s.at) / s.dur;
        if (k < 0 || k > 1) continue;
        const env = Math.pow(1 - k, 2) * s.amp;
        cx += vnoise(t * 38, sd + 5) * env / z; cy += vnoise(t * 41, sd + 9) * env / z; rot += vnoise(t * 30, sd + 13) * env * 0.04;
      }
      return { cx, cy, z, rot };
    }
  }

  /* ----------------------------------------------------------------- shot */
  let shotSeed = 1;
  class Shot {
    constructor(film, t0, t1, o = {}) {
      this.film = film; this.t0 = t0; this.t1 = t1; this.name = o.name || 'shot' + film.shots.length;
      this.seed = shotSeed++ * 7.7;
      this.ground = o.ground == null ? 300 : o.ground;
      this.sc = S.createScene(null, { duration: film.duration, ground: this.ground, groundLine: false, fadeIn: 0, fadeOut: 0 });
      this.groundLine = o.groundLine !== false;
      this.groundDraw = o.groundDraw || 0;          // seconds of draw-on at shot start (0 = already drawn)
      this.layers = [];
      this.tintOp = new Track(0); this.tintCol = [];
      this.cam = new Camera(this);
      if (o.frame) this.cam.set(o.frame);
      if (o.handheld) this.cam.handheld(o.handheld);
    }
    /** Scribble (or a side character). Same options as v1 sc.character, plus motion: {…} (see enhance). */
    character(o = {}) { const c = this.sc.character(o); return o.motion === false ? c : enhance(c, o.motion || {}); }
    prop(name, o) { return this.sc.prop(name, Object.assign({ y: this.ground }, o)); }
    text(str, o) { return this.sc.text(str, o); }
    custom(fn, layer = 'back') { this.sc.custom(fn, layer); return this; }
    /** Parallax layer. depth < 1 = far (moves less), > 1 = near/foreground. fn(t, view) → svg (world units). */
    layer(depth, fn, o = {}) { this.layers.push({ depth, fn, front: o.front != null ? o.front : depth > 1, blur: o.blur || 0, op: o.opacity == null ? 1 : o.opacity }); return this; }
    /** Colour light over the whole shot (multiply). Animate with several calls: tint(at, dur, '#B9C3D9', 0.3). */
    tint(at, dur, color, op) { this.tintOp.to(at, dur, op, 'inOut'); if (color) this.tintCol.push({ at, color }); this.tintCol.sort((a, b) => a.at - b.at); return this; }
    _tint(t) {
      if (!this.tintCol.length) return { color: null, op: 0 };
      let color = this.tintCol[0].color;
      for (const k of this.tintCol) if (t >= k.at) color = k.color;
      return { color, op: this.tintOp.at(t) };
    }
  }

  /* ---------------------------------------------------- transitions */
  const TR_DEFAULT_DUR = { cut: 0, smash: 0, dissolve: 0.6, dip: 0.8, whip: 0.42, iris: 1.0, ink: 1.0, page: 0.9, match: 0.5 };
  const TR_SFX = { whip: 'whip', ink: 'splat', page: 'page', iris: 'iris', smash: 'impact', match: 'swish', dip: null, dissolve: null, cut: null };

  function blobPath(cx, cy, R, seed, spikes = true) {
    const N = 56; const pts = [];
    for (let i = 0; i < N; i++) {
      const a = (i / N) * TAU;
      let r = R * (1 + 0.13 * Math.sin(a * 3 + seed) + 0.08 * Math.sin(a * 7 + seed * 2.3) + 0.05 * Math.sin(a * 13 + seed * 1.7));
      if (spikes && i % 7 === 3) r *= 1.16;
      pts.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]);
    }
    let d = '';
    for (let i = 0; i < N; i++) {
      const p = pts[i], q = pts[(i + 1) % N], m = [(p[0] + q[0]) / 2, (p[1] + q[1]) / 2];
      d += (i === 0 ? `M${f((pts[N - 1][0] + p[0]) / 2)} ${f((pts[N - 1][1] + p[1]) / 2)}` : '') + `Q${f(p[0])} ${f(p[1])} ${f(m[0])} ${f(m[1])}`;
    }
    return d + 'Z';
  }
  const rectPath = (v, m = 40) => `M${f(v.x - m)} ${f(v.y - m)}H${f(v.x + v.w + m)}V${f(v.y + v.h + m)}H${f(v.x - m)}Z`;

  /* ---------------------------------------------------------------- film */
  class Film {
    /**
     * Fabelo2.film(container, { duration, bpm, beatOffset, fadeIn, fadeOut, captions })
     * container = document.body for a page; null for headless (tests / svg export).
     */
    constructor(container, o = {}) {
      this.duration = o.duration || 30;
      this.bpm = o.bpm || 72;
      this.beatOffset = o.beatOffset || 0;
      this.fadeIn = o.fadeIn == null ? 0.9 : o.fadeIn;
      this.fadeOut = o.fadeOut == null ? 1.2 : o.fadeOut;
      this.shots = []; this.cuts = []; this.titles = []; this.huds = []; this.cues = [];
      this.capCfg = null;
      this.view = { x: -889, y: -500, w: 1778, h: 1000 };
      this.t = 0;
      if (container && typeof document !== 'undefined') {
        this.stage = S.createScene(container, { duration: this.duration, groundLine: false, fadeIn: this.fadeIn, fadeOut: this.fadeOut, loop: true });
        this.stage.render = (t) => this.render(t);
        // scale text and lines as pure geometry: hinted glyphs snap to whole pixels and wobble on a zoom
        if (this.stage.svg) { this.stage.svg.setAttribute('text-rendering', 'geometricPrecision'); this.stage.svg.setAttribute('shape-rendering', 'geometricPrecision'); }
        this.stage.fit();
      }
    }
    /* ---- timing helpers ---- */
    /** Time of beat n (music grid). */
    beat(n) { return this.beatOffset + (n * 60) / this.bpm; }
    /** Snap a time to the nearest beat (or to 1/div of a beat). */
    snap(t, div = 1) { const b = 60 / this.bpm / div; return this.beatOffset + Math.round((t - this.beatOffset) / b) * b; }
    /** A custom cue for the audio mix: film.cue('sfx', 12.3, {name:'thud', gain:0.4}). */
    cue(kind, at, data = {}) { this.cues.push(Object.assign({ kind, at }, data)); return this; }

    /* ---- building ---- */
    shot(t0, t1, o) { const s = new Shot(this, t0, t1, o); this.shots.push(s); this.shots.sort((a, b) => a.t0 - b.t0); return s; }
    /**
     * Transition at time `at` (the boundary between two shots).
     * type: cut | smash | dissolve | dip | whip | iris | ink | page | match
     * o: { dur, dir (whip/page: 1 = to the left), at: [x,y] screen point (iris/ink centre),
     *      color (dip/iris/ink: default ink), from:[x,y], to:[x,y] (match: world points), sfx:false }
     */
    cut(at, type = 'cut', o = {}) {
      const dur = o.dur != null ? o.dur : TR_DEFAULT_DUR[type] || 0;
      const c = Object.assign({ at, type, dur, dir: 1, color: C.ink, seed: this.cuts.length * 2.9 + 1 }, o, { at, type, dur });
      this.cuts.push(c); this.cuts.sort((a, b) => a.at - b.at);
      return this;
    }
    /** Screen-space handwritten title (not moved by the camera). */
    title(str, o = {}) {
      this.titles.push(Object.assign({ str, x: 0, y: -380, size: 72, at: 0, until: this.duration, write: 0.7, color: C.ink, weight: 700 }, o));
      return this;
    }
    /** Screen-space drawing on top of everything (lower thirds, logos): fn(t, view) → svg. */
    hud(fn) { this.huds.push(fn); return this; }
    /**
     * Word-by-word captions for Shorts.
     * lines: LINES array [speaker, start, end, text]; timing from window.__TIMING (voices.py) when present.
     * o: { speakers: ['narrator'] (null = all), y: 372, size: 74, maxWords: 3, maxWidth: 880, highlight: red }
     */
    captions(lines, o = {}) {
      this.capCfg = Object.assign({ speakers: null, y: 372, size: 74, maxWords: 3, maxWidth: 880, highlight: C.red, color: C.ink, stroke: C.paper }, o);
      this.capChunks = buildCaptionChunks(lines, this.capCfg, global.__TIMING);
      return this;
    }

    /* ---- rendering ---- */
    _shotAt(t) {
      let cur = null;
      for (const s of this.shots) if (t >= s.t0 - 1e-6) cur = s;
      return cur || this.shots[0];
    }
    _shotBefore(at) { let p = null; for (const s of this.shots) if (s.t0 < at - 1e-6) p = s; return p; }
    _shotFrom(at) { for (const s of this.shots) if (s.t0 >= at - 1e-6) return s; return null; }

    /** World → screen point for a shot at time t. */
    toScreen(shot, t, p) {
      const c = shot.cam.at(t, this.view), r = (c.rot * Math.PI) / 180;
      const x = (p[0] - c.cx) * c.z, y = (p[1] - c.cy) * c.z;
      return [x * Math.cos(r) - y * Math.sin(r), x * Math.sin(r) + y * Math.cos(r)];
    }

    _shotSVG(sh, t, v, uid) {
      const c = sh.cam.at(t, v);
      const tr = (d) => {
        const zd = 1 + (c.z - 1) * d;
        return { zd, s: `rotate(${fp(c.rot)}) scale(${fp(zd)}) translate(${fp(-c.cx * d)} ${fp(-c.cy * d)})`, view: { x: c.cx * d - v.w / (2 * zd), y: c.cy * d - v.h / (2 * zd), w: v.w / zd, h: v.h / zd } };
      };
      let defs = '', out = '';
      const layerSVG = (L, i) => {
        const T = tr(L.depth);
        let body = L.fn(t, T.view, sh);
        if (!body) return '';
        let attr = '';
        if (L.blur > 0) { const id = `${uid}b${i}`; defs += `<filter id="${id}" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="${fp(L.blur / T.zd)}"/></filter>`; attr += ` filter="url(#${id})"`; }
        if (L.op < 1) attr += ` opacity="${f(L.op)}"`;
        return `<g transform="${T.s}"${attr}>${body}</g>`;
      };
      sh.layers.forEach((L, i) => { if (!L.front) out += layerSVG(L, i); });
      // main stage (depth 1): ground line, v1 customs, props, characters, texts
      const T1 = tr(1), wv = T1.view, sc = sh.sc;
      const proxy = Object.create(sc); proxy.view = wv;
      let s = '';
      if (sh.groundLine) {
        const k = sh.groundDraw > 0 ? clamp((t - sh.t0) / sh.groundDraw) : 1;
        if (k > 0) {
          const x0 = wv.x - 60, x1 = wv.x + wv.w + 60, gy = sh.ground;
          const dash = k < 1 ? ` class="sb-draw" style="--o:${f(1 - E.inOut(k))};--fo:1"` : '';
          s += `<g${dash}>` + sv.path(`M${f(x0)} ${gy + 4} Q${f((x0 + x1) / 2)} ${gy - 2} ${f(x1)} ${gy + 3}`, { w: 4, op: 0.55 }) + `</g>`;
        }
      }
      for (const cu of sc.customs) if (cu.layer === 'back') s += cu.fn(t, proxy);
      for (const p of sc.props) if (!p.front) s += sc._propSvg(p, t);
      for (const ch of sc.chars) { const r = ch.render(t); if (r) s += `<g data-qc="char">${r}</g>`; }
      for (const p of sc.props) if (p.front) s += sc._propSvg(p, t);
      for (const cu of sc.customs) if (cu.layer === 'front') s += cu.fn(t, proxy);
      sc.texts.forEach((tx, i) => (s += sc._textSvg(tx, i, t)));
      out += `<g transform="${T1.s}">${s}</g>`;
      sh.layers.forEach((L, i) => { if (L.front) out += layerSVG(L, i); });
      const ti = sh._tint(t);
      if (ti.color && ti.op > 0.004) out += `<rect x="${f(v.x - 20)}" y="${f(v.y - 20)}" width="${f(v.w + 40)}" height="${f(v.h + 40)}" fill="${ti.color}" style="mix-blend-mode:multiply" opacity="${f(ti.op)}"/>`;
      return (defs ? `<defs>${defs}</defs>` : '') + out;
    }

    _transitionSVG(cu, t, v) {
      const A = this._shotBefore(cu.at), B = this._shotFrom(cu.at);
      const a0 = cu.at - cu.dur / 2;
      const p = clamp((t - a0) / Math.max(1e-3, cu.dur));
      const out = () => (A ? this._shotSVG(A, t, v, 'tA') : '');
      const inn = () => (B ? this._shotSVG(B, t, v, 'tB') : '');
      const R = Math.hypot(v.w, v.h) / 2 + 80;
      const cxy = cu.center || [0, 0];
      switch (cu.type) {
        case 'dissolve': {
          const k = E.sineInOut(p);
          return out() + `<g opacity="${f(k)}">${inn()}</g>`;
        }
        case 'dip': {
          const k = p < 0.5 ? E.inOut(p * 2) : E.inOut((1 - p) * 2);
          const col = cu.color === C.ink && cu.paper !== false ? C.paper : cu.color;
          return (p < 0.5 ? out() : inn()) + `<rect x="${f(v.x - 20)}" y="${f(v.y - 20)}" width="${f(v.w + 40)}" height="${f(v.h + 40)}" fill="${col}" opacity="${f(k)}"/>`;
        }
        case 'whip': {
          const first = p < 0.5;
          const k = first ? E.expoIn(p * 2) : 1 - E.expoOut((p - 0.5) * 2);
          const dx = (first ? -1 : 1) * cu.dir * k * v.w * 0.62;
          const blur = 3 + 55 * k;
          return `<defs><filter id="whipF" x="-50%" y="-10%" width="200%" height="120%"><feGaussianBlur stdDeviation="${f(blur)} 0"/></filter></defs>` +
            `<g transform="translate(${fp(dx)} 0)" filter="url(#whipF)">${first ? out() : inn()}</g>`;
        }
        case 'iris': {
          const first = p < 0.5;
          const k = first ? 1 - E.inOut(p * 2) : E.inOut((p - 0.5) * 2);
          const r = Math.max(0, R * k);
          const c0 = first ? (cu.from || cxy) : (cu.to || cxy);
          const hole = r > 0.5 ? `M${f(c0[0] - r)} ${f(c0[1])}a${f(r)} ${f(r)} 0 1 0 ${f(2 * r)} 0a${f(r)} ${f(r)} 0 1 0 ${f(-2 * r)} 0Z` : '';
          const ring = r > 0.5 ? `<circle cx="${f(c0[0])}" cy="${f(c0[1])}" r="${f(r)}" fill="none" stroke="${C.ink}" stroke-width="7" opacity="0.6"/>` : '';
          return (first ? out() : inn()) + `<path d="${rectPath(v)}${hole}" fill="${cu.color}" fill-rule="evenodd"/>` + ring;
        }
        case 'ink': {
          const first = p < 0.5;
          const c0 = first ? (cu.from || cxy) : (cu.to || cxy);
          if (first) {
            const k = E.expoIn(clamp(p * 2));
            const r = R * 1.3 * k;
            let drops = '';
            for (let i = 0; i < 12; i++) {
              const a = hash(i + cu.seed) * Math.PI, dd = r * (1.15 + 0.35 * Math.abs(hash(i * 3.1 + cu.seed))), rr = R * 0.035 * (0.5 + Math.abs(hash(i * 1.7))) * Math.min(1, k * 3);
              drops += `<circle cx="${f(c0[0] + Math.cos(a * 2) * dd)}" cy="${f(c0[1] + Math.sin(a * 2) * dd)}" r="${f(rr)}" fill="${cu.color}"/>`;
            }
            return out() + (r > 1 ? `<path d="${blobPath(c0[0], c0[1], r, cu.seed)}" fill="${cu.color}"/>` + drops : '');
          }
          const k = E.expoOut(clamp((p - 0.5) * 2));
          const r = R * 1.35 * k;
          return inn() + `<path d="${rectPath(v)}${r > 1 ? blobPath(c0[0], c0[1], r, cu.seed + 5, false) : ''}" fill="${cu.color}" fill-rule="evenodd"/>`;
        }
        case 'page': {
          const e = E.inOut(p), dir = cu.dir >= 0 ? 1 : -1;
          // fold line moves across the screen; outgoing page stays on the near side, its back curls over
          const L = v.x, Rr = v.x + v.w, W = v.w;
          const xf = dir > 0 ? Rr - e * (W * 1.25) : L + e * (W * 1.25);
          const curl = Math.sin(Math.PI * e) * v.h * 0.08;
          const xt = xf + curl * dir, xb = xf - curl * dir;           // top / bottom of the fold
          const keep = dir > 0 ? `M${f(L - 40)} ${f(v.y - 40)}L${f(xt)} ${f(v.y - 40)}L${f(xb)} ${f(v.y + v.h + 40)}L${f(L - 40)} ${f(v.y + v.h + 40)}Z`
            : `M${f(Rr + 40)} ${f(v.y - 40)}L${f(xt)} ${f(v.y - 40)}L${f(xb)} ${f(v.y + v.h + 40)}L${f(Rr + 40)} ${f(v.y + v.h + 40)}Z`;
          const fw = Math.min(Math.abs((dir > 0 ? Rr : L) - xf), W * 0.42) * 0.85;
          const flap = `M${f(xt)} ${f(v.y - 40)}L${f(xt - dir * fw * 1.1)} ${f(v.y - 40)}Q${f(xb - dir * fw * 0.7)} ${f(v.y + v.h * 0.5)} ${f(xb - dir * fw * 0.9)} ${f(v.y + v.h + 40)}L${f(xb)} ${f(v.y + v.h + 40)}Z`;
          const gid = 'pgG', sid = 'pgS';
          return `<defs><clipPath id="pgC"><path d="${keep}"/></clipPath>` +
            `<linearGradient id="${gid}" x1="${dir > 0 ? 1 : 0}" y1="0" x2="${dir > 0 ? 0 : 1}" y2="0"><stop offset="0" stop-color="#FFFDF7"/><stop offset="0.55" stop-color="${C.paperDark}"/><stop offset="1" stop-color="#D9CCB0"/></linearGradient>` +
            `<linearGradient id="${sid}" x1="${dir > 0 ? 0 : 1}" y1="0" x2="${dir > 0 ? 1 : 0}" y2="0"><stop offset="0" stop-color="#3a2f1c" stop-opacity="0.28"/><stop offset="1" stop-color="#3a2f1c" stop-opacity="0"/></linearGradient></defs>` +
            inn() +
            `<rect x="${f(dir > 0 ? xf - 10 : xf - 90)}" y="${f(v.y - 40)}" width="100" height="${f(v.h + 80)}" fill="url(#${sid})"/>` +
            `<g clip-path="url(#pgC)">${out()}</g>` +
            (fw > 2 ? `<path d="${flap}" fill="url(#${gid})" stroke="${C.ink}" stroke-width="3" stroke-opacity="0.35"/>` : '');
        }
        case 'match': {
          const sA = A && cu.from ? this.toScreen(A, t, cu.from) : [0, 0], sB = B && cu.to ? this.toScreen(B, t, cu.to) : sA;
          const kz = E.inOut(p);
          const zA = 1 + 0.35 * kz, zB = 1.35 - 0.35 * kz;
          const mix = E.sineInOut(clamp((p - 0.3) / 0.4));
          const g = (pt, z) => `translate(${fp(pt[0])} ${fp(pt[1])}) scale(${fp(z)}) translate(${fp(-pt[0])} ${fp(-pt[1])})`;
          return `<g transform="${g(sA, zA)}">${out()}</g><g transform="${g(sB, zB)}" opacity="${f(mix)}">${inn()}</g>`;
        }
        default: return t < cu.at ? out() : inn();
      }
    }

    _titleSVG(tx, i, t) {
      if (t < tx.at || t > tx.until) return '';
      const op = Math.min(clamp((t - tx.at) / 0.35), clamp((tx.until - t) / 0.4));
      const k = tx.write > 0 ? E.quintOut(clamp((t - tx.at) / tx.write)) : 1;
      const wEst = measure(tx.str, tx.size) + tx.size;
      const id = `ft${i}`;
      return `<g data-qc="hud"><clipPath id="${id}"><rect x="${f(tx.x - wEst / 2)}" y="${f(tx.y - tx.size * 1.2)}" width="${f(wEst * k)}" height="${f(tx.size * 1.8)}"/></clipPath>` +
        `<text x="${f(tx.x)}" y="${f(tx.y)}" text-anchor="middle" font-family="Caveat, cursive" font-size="${tx.size}" font-weight="${tx.weight}" fill="${tx.color}" opacity="${f(op)}" clip-path="url(#${id})" paint-order="stroke" stroke="${C.paper}" stroke-width="${f(tx.size * 0.12)}" stroke-linejoin="round">${esc(tx.str)}</text></g>`;
    }

    _captionSVG(t) {
      const cfg = this.capCfg; if (!cfg || !this.capChunks) return '';
      const ch = this.capChunks.find((c) => t >= c.t0 && t < c.t1);
      if (!ch) return '';
      const fin = E.backOut(clamp((t - ch.t0) / 0.18)), fout = clamp((ch.t1 - t) / 0.12);
      let size = cfg.size;
      const space = size * 0.28;
      const widths = ch.words.map((w) => measure(w.w, size));
      let total = widths.reduce((a, b) => a + b, 0) + space * (ch.words.length - 1);
      if (total > cfg.maxWidth) { const k = cfg.maxWidth / total; size *= k; widths.forEach((w, i) => (widths[i] = w * k)); total = cfg.maxWidth; }
      let x = -total / 2, s = '';
      ch.words.forEach((w, i) => {
        const active = t >= w.t0 && t < (i + 1 < ch.words.length ? ch.words[i + 1].t0 : ch.t1);
        const said = t >= w.t0;
        const pop = active ? 1 + 0.14 * Math.sin(Math.PI * clamp((t - w.t0) / 0.22)) : 1;
        const cx = x + widths[i] / 2;
        s += `<text x="${f(cx)}" y="0" text-anchor="middle" transform="translate(0 0) scale(1)" font-family="Caveat, cursive" font-weight="700" font-size="${f(size * pop)}" fill="${active ? cfg.highlight : cfg.color}" opacity="${said ? 1 : 0.55}" paint-order="stroke" stroke="${cfg.stroke}" stroke-width="${f(size * 0.16)}" stroke-linejoin="round">${esc(w.w)}</text>`;
        x += widths[i] + space;
      });
      const sc = 0.86 + 0.14 * fin;
      return `<g data-qc="cap" transform="translate(0 ${f(cfg.y)}) scale(${fp(sc)})" opacity="${f(Math.min(1, fin * 1.4) * fout)}">${s}</g>`;
    }

    /** Full frame contents (inside the stage root) at time t. */
    frame(t) {
      const v = (this.stage && this.stage.view) || this.view;
      this.view = v;
      let s = '';
      const cu = this.cuts.find((c) => c.dur > 0 && t >= c.at - c.dur / 2 && t < c.at + c.dur / 2);
      if (cu) s += this._transitionSVG(cu, t, v);
      else { const sh = this._shotAt(t); if (sh) s += this._shotSVG(sh, t, v, 'tS'); }
      // smash cut: one bright frame + shake is added by the incoming shot's camera
      for (const c of this.cuts) if (c.type === 'smash' && t >= c.at && t < c.at + 0.12) s += `<rect x="${f(v.x - 20)}" y="${f(v.y - 20)}" width="${f(v.w + 40)}" height="${f(v.h + 40)}" fill="#FFFFFF" opacity="${f(0.85 * (1 - (t - c.at) / 0.12))}"/>`;
      for (const h of this.huds) s += h(t, v) || '';
      this.titles.forEach((tx, i) => (s += this._titleSVG(tx, i, t)));
      s += this._captionSVG(t);
      return s;
    }

    render(t) {
      this.t = t;
      const st = this.stage;
      if (!st || !st.root) return;
      st.t = t;
      const D = this.duration;
      const fi = this.fadeIn > 0 ? E.quintOut(clamp(t / this.fadeIn)) : 1;
      const fo = this.fadeOut > 0 ? E.sineInOut(clamp((D - t) / this.fadeOut)) : 1;
      const op = Math.min(fi, fo);
      st.root.setAttribute('opacity', fp(op));
      st.root.setAttribute('transform', `scale(${fp(0.92 + 0.08 * op)})`);
      st.root.innerHTML = `<g>${this.frame(t)}</g>`;
    }

    /** Standalone SVG of one frame (headless previews / thumbnails). */
    svgFrame(t, W = 1080, H = 1920) {
      const a = W / H, vw = a >= 1 ? 1000 * a : 1000, vh = a >= 1 ? 1000 : 1000 / a;
      this.view = { x: -vw / 2, y: -vh / 2, w: vw, h: vh };
      const D = this.duration;
      const op = Math.min(this.fadeIn > 0 ? E.quintOut(clamp(t / this.fadeIn)) : 1, this.fadeOut > 0 ? E.sineInOut(clamp((D - t) / this.fadeOut)) : 1);
      return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="${f(-vw / 2)} ${f(-vh / 2)} ${f(vw)} ${f(vh)}">` +
        `<style>.sb-draw [pathLength]{stroke-dasharray:1 1;stroke-dashoffset:var(--o)}.sb-draw .f{fill-opacity:var(--fo)}</style>` +
        `<rect x="${f(-vw / 2)}" y="${f(-vh / 2)}" width="${f(vw)}" height="${f(vh)}" fill="${C.paper}"/>` +
        `<g opacity="${fp(op)}" transform="scale(${fp(0.92 + 0.08 * op)})">${this.frame(t)}</g></svg>`;
    }

    /** Make the page recordable (record.js / record2.js) and play or freeze (?t=). */
    ready(lines) {
      for (const c of this.cuts) if (c.type === 'smash' && !c._shook) { const B = this._shotFrom(c.at); if (B) B.cam.shake(c.at, 0.35, c.shake || 16); c._shook = true; }
      const cues = [];
      for (const c of this.cuts) cues.push({ kind: 'transition', type: c.type, at: c.at, dur: c.dur, sfx: c.sfx === false ? null : (c.sfx || TR_SFX[c.type] || null), x: c.center ? c.center[0] : 0 });
      for (const s of this.shots) cues.push({ kind: 'shot', name: s.name, at: s.t0, end: s.t1 });
      for (const c of this.cues) cues.push(c);
      cues.sort((a, b) => a.at - b.at);
      if (typeof window !== 'undefined') {
        window.__LINES = lines || window.__LINES || [];
        window.__CUES = { bpm: this.bpm, beatOffset: this.beatOffset, duration: this.duration, cues };
        window.__FILM = this;
      }
      if (this.stage) {
        this.stage.exposeForRecording();
        const q = new URLSearchParams(location.search);
        if (q.has('t')) this.stage.seek(parseFloat(q.get('t'))); else this.stage.play();
      }
      return this;
    }
  }

  /* -------------------------------------------------------- captions */
  const esc = (s) => String(s).replace(/[<>&"']/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&#39;' }[c]));
  let mctx = null; const mcache = {};
  function measure(str, size) {
    const key = size + '|' + str;
    if (mcache[key]) return mcache[key];
    let w = null;
    if (typeof document !== 'undefined') {
      try {
        mctx = mctx || document.createElement('canvas').getContext('2d');
        mctx.font = `700 ${size}px Caveat, cursive`;
        w = mctx.measureText(str).width;
        if (document.fonts && document.fonts.status === 'loaded') mcache[key] = w;
      } catch (e) { w = null; }
    }
    if (w == null) w = str.length * size * 0.43;
    return w;
  }
  // syllable-ish weight for a word (longer words take longer to say)
  const wWeight = (w) => Math.max(1, (w.replace(/[^a-z]/gi, '').match(/[aeiouy]+/gi) || []).length) + w.length * 0.08;
  function estimateWords(text, t0, t1) {
    const words = text.split(/\s+/).filter(Boolean);
    const pauses = words.map((w) => (/[,;:]$/.test(w) ? 0.6 : /[.!?…]$/.test(w) ? 0.9 : 0));
    const tot = words.reduce((a, w, i) => a + wWeight(w) + (i < words.length - 1 ? pauses[i] : 0), 0);
    let t = t0; const out = [];
    words.forEach((w, i) => {
      const d = ((wWeight(w)) / tot) * (t1 - t0);
      out.push({ w, t0: t, t1: t + d });
      t += d + (i < words.length - 1 ? (pauses[i] / tot) * (t1 - t0) : 0);
    });
    return out;
  }
  function buildCaptionChunks(lines, cfg, timing) {
    const chunks = [];
    lines.forEach((ln, idx) => {
      const [who, st, en, text] = ln;
      if (cfg.speakers && cfg.speakers.indexOf(who) < 0) return;
      let words = null;
      const tl = timing && timing.lines && timing.lines.find((x) => x.i === idx && x.text === text);
      if (tl && tl.words && tl.words.length) words = tl.words.map((w) => ({ w: w[0], t0: w[1], t1: w[2] }));
      else words = estimateWords(text, st + 0.05, tl ? tl.start + tl.dur : en);
      let cur = [];
      const flush = () => { if (cur.length) chunks.push({ words: cur, t0: cur[0].t0 - 0.06, t1: cur[cur.length - 1].t1 + 0.12 }); cur = []; };
      words.forEach((w) => {
        cur.push(w);
        const chars = cur.reduce((a, x) => a + x.w.length, 0);
        if (cur.length >= cfg.maxWords || chars >= 15 || /[,.!?;:…]$/.test(w.w)) flush();
      });
      flush();
    });
    // chunks never overlap: each ends where the next begins (if close), and lingers at most 0.6 s
    for (let i = 0; i < chunks.length; i++) {
      const n = chunks[i + 1];
      if (n && chunks[i].t1 > n.t0) chunks[i].t1 = n.t0;
      if (n && n.t0 - chunks[i].t1 < 0.25) chunks[i].t1 = n.t0;
    }
    return chunks;
  }

  /* ------------------------------------------------- scenery helpers */
  // Ink-on-paper backgrounds for parallax layers. Each returns svg in world units.
  const bg = {
    hills(view, o = {}) {
      const y = o.y == null ? 300 : o.y, h = o.h || 120, seed = o.seed || 1, col = o.fill || C.paperDark;
      const x0 = view.x - 100, x1 = view.x + view.w + 100, n = 14;
      let d = `M${f(x0)} ${f(y + 2000)}L${f(x0)} ${f(y)}`;
      for (let i = 0; i <= n; i++) { const x = lerp(x0, x1, i / n); d += `L${f(x)} ${f(y - h * (0.5 + 0.5 * fbm(x * 0.004 + seed, seed)))}`; }
      d += `L${f(x1)} ${f(y + 2000)}Z`;
      return `<path d="${d}" fill="${col}" stroke="${C.ink}" stroke-width="${o.w || 3}" stroke-opacity="${o.op == null ? 0.35 : o.op}" stroke-linejoin="round"/>`;
    },
    clouds(t, view, o = {}) {
      const n = o.n || 4, y = o.y == null ? -330 : o.y, sp = o.speed == null ? 8 : o.speed;
      let s = '';
      for (let i = 0; i < n; i++) {
        const span = view.w + 600, x = view.x - 300 + (((i * span) / n + t * sp + hash(i) * 200) % span + span) % span;
        const yy = y + hash(i * 3.3) * 60, sc = 0.8 + 0.35 * Math.abs(hash(i * 1.9));
        s += sv.g(S.propSVG('cloud', t), `translate(${f(x)} ${f(yy)}) scale(${f(sc)})`, ' opacity="0.8"');
      }
      return s;
    },
    rain(t, view, o = {}) {
      const n = o.n || 70, len = o.len || 34, sp = o.speed || 1400, op = o.op == null ? 0.35 : o.op;
      let d = '';
      for (let i = 0; i < n; i++) {
        const x = view.x + ((hash(i) * 0.5 + 0.5) * view.w), y0 = view.y + ((((hash(i * 7.1) * 0.5 + 0.5) * view.h + t * sp) % (view.h + 100)) - 50);
        d += `M${f(x)} ${f(y0)}l${f(-len * 0.18)} ${f(len)}`;
      }
      return `<path d="${d}" stroke="${o.color || C.blue}" stroke-width="${o.w || 3}" stroke-linecap="round" opacity="${op}" fill="none"/>`;
    },
    stars(t, view, o = {}) {
      const n = o.n || 40; let s = '';
      for (let i = 0; i < n; i++) {
        const x = view.x + (hash(i * 2.3) * 0.5 + 0.5) * view.w, y = view.y + (hash(i * 5.7) * 0.5 + 0.5) * view.h * 0.55;
        const tw = 0.4 + 0.6 * Math.abs(Math.sin(t * (1 + Math.abs(hash(i))) + i));
        s += `<circle cx="${f(x)}" cy="${f(y)}" r="${f(2 + 2 * Math.abs(hash(i * 9.1)))}" fill="${o.color || '#FFF6D8'}" opacity="${f(tw)}"/>`;
      }
      return s;
    },
    sky(view, color, op = 1) { return `<rect x="${f(view.x - 50)}" y="${f(view.y - 50)}" width="${f(view.w + 100)}" height="${f(view.h + 100)}" fill="${color}" opacity="${op}"/>`; },
    floorboards(view, o = {}) {
      const y = o.y == null ? 300 : o.y; let d = '';
      for (let i = 1; i < 5; i++) { const yy = y + i * i * 14; d += `M${f(view.x - 50)} ${f(yy)}L${f(view.x + view.w + 50)} ${f(yy)}`; }
      return `<path d="${d}" stroke="${C.ink}" stroke-width="3" opacity="0.18" fill="none"/>`;
    }
  };

  const Fabelo2 = {
    version: '2.0.0',
    film: (container, o) => new Film(container, o),
    enhance, spring, bg, EASE: E, noise: vnoise, fbm, hash,
    TRANSITIONS: Object.keys(TR_DEFAULT_DUR), TR_SFX,
    _estimateWords: estimateWords, _buildCaptionChunks: buildCaptionChunks
  };
  global.Fabelo2 = Fabelo2;
  if (typeof module !== 'undefined' && module.exports) module.exports = Fabelo2;
})(typeof window !== 'undefined' ? window : globalThis);
