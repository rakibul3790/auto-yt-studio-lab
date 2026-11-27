/*!
 * Scribble — character library for ink-style explainer videos (v1.1)
 *
 * One recurring character ("Scribble": ink stick figure with a red scarf),
 * a bendable rig, poses, expressions, costumes, props and a time-based
 * scene engine. Everything on screen is a pure function of time t (seconds),
 * so a headless browser can seek to any frame and record it exactly.
 *
 * No dependencies. Works in any modern browser.
 * See README.md for the full API.
 */
(function (global) {
  'use strict';

  /* ------------------------------------------------------------------ *
   * Palette — the channel uses ink + paper + ONE accent (red).
   * Ochre is only for fire, light and gold.
   * ------------------------------------------------------------------ */
  const C = {
    ink: '#1B1B1B',
    paper: '#FBF7EE',
    paperDark: '#EDE4D0',
    red: '#E63946',
    ochre: '#E9B44C',
    grey: '#9A9A9A',
    brown: '#C98B5B',
    darkBrown: '#8A5A35',
    blue: '#2B4C7E',
    green: '#6A994E',
    white: '#FFFFFF'
  };
  const SW = 7; // main ink stroke width (character units)

  /* ------------------------------------------------------------------ *
   * Math helpers
   * ------------------------------------------------------------------ */
  const rad = (d) => (d * Math.PI) / 180;
  const dir = (a, len) => [Math.sin(rad(a)) * len, Math.cos(rad(a)) * len]; // a=0 → down, a=90 → right
  const lerp = (a, b, k) => a + (b - a) * k;
  const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
  const f = (n) => Math.round(n * 100) / 100;
  const EASE = {
    linear: (k) => k,
    in: (k) => k * k * k,
    out: (k) => 1 - Math.pow(1 - k, 3),
    inOut: (k) => (k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2),
    back: (k) => {
      const c1 = 1.70158, c3 = c1 + 1;
      return 1 + c3 * Math.pow(k - 1, 3) + c1 * Math.pow(k - 1, 2);
    }
  };
  // smooth 0→1→0 window for [t0,t1] with ramps of r seconds
  const windowW = (t, t0, t1, r) => clamp(Math.min((t - t0) / r, (t1 - t) / r));

  /* ------------------------------------------------------------------ *
   * SVG builders. Every ink element gets pathLength="1" so the whole
   * drawing can "draw itself" with one CSS variable (--o).
   * ------------------------------------------------------------------ */
  const P = 'pathLength="1"';
  const line = (x1, y1, x2, y2, w = SW, c = C.ink) =>
    `<path ${P} d="M${f(x1)} ${f(y1)} L${f(x2)} ${f(y2)}" stroke="${c}" stroke-width="${w}" fill="none" stroke-linecap="round"/>`;
  const poly = (pts, w = SW, c = C.ink) =>
    `<path ${P} d="M${pts.map((p) => f(p[0]) + ' ' + f(p[1])).join(' L')}" stroke="${c}" stroke-width="${w}" fill="none" stroke-linecap="round" stroke-linejoin="round"/>`;
  const path = (d, o = {}) =>
    `<path ${P} d="${d}" fill="${o.fill || 'none'}"${o.fill && o.fill !== 'none' ? ' class="f"' : ''} stroke="${o.stroke || C.ink}" stroke-width="${o.w == null ? 5 : o.w}" stroke-linecap="round" stroke-linejoin="round"${o.op != null ? ` opacity="${o.op}"` : ''}/>`;
  const fillOnly = (d, fill, op) =>
    `<path d="${d}" fill="${fill}" class="f" stroke="none"${op != null ? ` opacity="${op}"` : ''}/>`;
  const circle = (cx, cy, r, o = {}) =>
    `<circle ${P} cx="${f(cx)}" cy="${f(cy)}" r="${f(r)}" fill="${o.fill || 'none'}"${o.fill && o.fill !== 'none' ? ' class="f"' : ''} stroke="${o.stroke || C.ink}" stroke-width="${o.w == null ? 5 : o.w}"/>`;
  const dot = (cx, cy, r, fill = C.ink) => `<circle cx="${f(cx)}" cy="${f(cy)}" r="${f(r)}" fill="${fill}" class="f"/>`;
  const ellipse = (cx, cy, rx, ry, fill = C.ink) =>
    `<ellipse cx="${f(cx)}" cy="${f(cy)}" rx="${f(rx)}" ry="${f(ry)}" fill="${fill}" class="f"/>`;
  const g = (inner, transform, extra = '') => `<g${transform ? ` transform="${transform}"` : ''}${extra}>${inner}</g>`;

  /* ------------------------------------------------------------------ *
   * Rig dimensions (character units; origin = ground point under hips)
   * ------------------------------------------------------------------ */
  const RIG = { torso: 50, neck: 16, headR: 30, upperArm: 28, foreArm: 28, thigh: 29, shin: 29, foot: 10 };

  /* ------------------------------------------------------------------ *
   * POSES. Angles in degrees: 0 = straight down, 90 = toward screen
   * right, 180 = straight up. Arms are relative to the torso, legs are
   * world-relative. [upper, lower] per limb. Hips auto-adjust so the
   * lowest foot stays on the ground (sitting, crouching just work).
   * aL/lL = limb on the screen-left side when facing right.
   * ------------------------------------------------------------------ */
  const POSES = {
    idle:     { lean: 0,  head: 0,   aL: [-28, -20],  aR: [28, 20],   lL: [-12, -14], lR: [12, 14] },
    wave:     { lean: -3, head: -4,  aL: [-28, -20],  aR: [100, 150], lL: [-12, -14], lR: [12, 14] },
    point:    { lean: 3,  head: 6,   aL: [-45, 30],   aR: [100, 100], lL: [-12, -14], lR: [14, 18] },
    pointUp:  { lean: 2,  head: -6,  aL: [-28, -20],  aR: [100, 170], lL: [-12, -14], lR: [12, 14] },
    explain:  { lean: 0,  head: -3,  aL: [-55, -115], aR: [55, 115],  lL: [-12, -14], lR: [12, 14] },
    shrug:    { lean: 0,  head: 10,  aL: [-95, -145], aR: [95, 145],  lL: [-10, -12], lR: [10, 12] },
    shocked:  { lean: -4, head: -6,  aL: [-120, -150],aR: [120, 150], lL: [-22, -26], lR: [22, 26] },
    think:    { lean: 0,  head: 8,   aL: [-25, -60],  aR: [70, 212],  lL: [-12, -14], lR: [12, 14] },
    sad:      { lean: 6,  head: 14,  aL: [-18, -10],  aR: [18, 10],    lL: [-8, -8],   lR: [8, 8] },
    cheer:    { lean: 0,  head: -8,  aL: [-125, -150],aR: [125, 150], lL: [-16, -30], lR: [16, 30], jump: 10 },
    facepalm: { lean: 6,  head: 16,  aL: [-28, -20],  aR: [165, 190], lL: [-12, -14], lR: [12, 14] },
    sit:      { lean: -4, head: 0,   aL: [20, 40],    aR: [25, 45],   lL: [85, 0],    lR: [95, 8] },
    write:    { lean: 10, head: 14,  aL: [-20, -10],  aR: [60, 95],   lL: [-12, -14], lR: [12, 14] },
    carry:    { lean: -4, head: 0,   aL: [40, 115],   aR: [50, 120],  lL: [-12, -14], lR: [12, 14] },
    scared:   { lean: -8, head: -8,  aL: [-35, -165], aR: [35, 165],  lL: [-25, 10],  lR: [25, -10] },
    hold:     { lean: 0,  head: 0,   aL: [-28, -20],  aR: [40, 120],  lL: [-12, -14], lR: [12, 14] },
    crouch:   { lean: 18, head: -10, aL: [30, 60],    aR: [40, 70],   lL: [70, -20],  lR: [80, -10] },
    victory:  { lean: -2, head: -6,  aL: [-28, -20],  aR: [100, 172], lL: [-14, -16], lR: [14, 16] },
    pray:     { lean: 2,  head: 10,  aL: [-50, 120],  aR: [50, -120], lL: [-10, -12], lR: [10, 12] },
    lie:      { lean: 0,  head: 0,   aL: [-8, -4],    aR: [8, 4],     lL: [-3, -3],   lR: [3, 3] },
    sitUp:    { lean: -6, head: 0,   aL: [25, 40],    aR: [30, 45],   lL: [90, 92],   lR: [88, 90] }
  };

  /* ------------------------------------------------------------------ *
   * EXPRESSIONS: eyes, brows {lift, tilt}, mouth, look offset.
   * tilt > 0 raises the inner ends (worried), tilt < 0 lowers them (angry).
   * ------------------------------------------------------------------ */
  const EXPRESSIONS = {
    neutral:  { eyes: 'dot',    brows: { lift: 0, tilt: 0 },   mouth: 'smile' },
    happy:    { eyes: 'arc',    brows: { lift: -3, tilt: 0 },  mouth: 'grin' },
    shocked:  { eyes: 'wide',   brows: { lift: -8, tilt: 0 },  mouth: 'o' },
    sad:      { eyes: 'dot',    brows: { lift: -1, tilt: 14 }, mouth: 'frown', look: [0, 2] },
    angry:    { eyes: 'dot',    brows: { lift: 2, tilt: -18 }, mouth: 'flat' },
    thinking: { eyes: 'dot',    brows: { lift: -2, tilt: 0, raise: 'right' }, mouth: 'side', look: [3, -4] },
    smirk:    { eyes: 'dot',    brows: { lift: -1, tilt: 0, raise: 'left' },  mouth: 'smirk' },
    scared:   { eyes: 'wide',   brows: { lift: -6, tilt: 14 }, mouth: 'wavy' },
    sleepy:   { eyes: 'half',   brows: { lift: 2, tilt: 0 },   mouth: 'smallO' },
    excited:  { eyes: 'wide',   brows: { lift: -6, tilt: 0 },  mouth: 'grin' },
    confused: { eyes: 'dot',    brows: { lift: -2, tilt: 0, raise: 'left' },  mouth: 'wavy', look: [-2, 0] },
    proud:    { eyes: 'closed', brows: { lift: -2, tilt: 0 },  mouth: 'grin' },
    calm:     { eyes: 'closed', brows: { lift: 0, tilt: 4 },   mouth: 'smile' }
  };

  /* ------------------------------------------------------------------ *
   * Face drawing (head-local coords: centre 0,0, radius 30)
   * ------------------------------------------------------------------ */
  function drawFace(e, look, blink, talkOpen) {
    const lx = look[0], ly = look[1];
    let s = '';
    const ex = 10, ey = -2;
    // eyes
    let eyes = blink && e.eyes !== 'arc' && e.eyes !== 'closed' ? 'closed' : e.eyes;
    if (eyes === 'dot') s += dot(-ex + lx, ey + ly, 4) + dot(ex + lx, ey + ly, 4);
    else if (eyes === 'wide') {
      s += circle(-ex + lx * 0.5, ey - 1, 7, { fill: C.white, w: 3 }) + circle(ex + lx * 0.5, ey - 1, 7, { fill: C.white, w: 3 });
      s += dot(-ex + lx, ey - 1 + ly * 0.5, 2.5) + dot(ex + lx, ey - 1 + ly * 0.5, 2.5);
    } else if (eyes === 'arc') {
      s += path(`M${-ex - 5 + lx} ${ey + 2} Q${-ex + lx} ${ey - 5} ${-ex + 5 + lx} ${ey + 2}`, { w: 3.5 });
      s += path(`M${ex - 5 + lx} ${ey + 2} Q${ex + lx} ${ey - 5} ${ex + 5 + lx} ${ey + 2}`, { w: 3.5 });
    } else if (eyes === 'closed') {
      s += path(`M${-ex - 5 + lx} ${ey} Q${-ex + lx} ${ey + 3} ${-ex + 5 + lx} ${ey}`, { w: 3.5 });
      s += path(`M${ex - 5 + lx} ${ey} Q${ex + lx} ${ey + 3} ${ex + 5 + lx} ${ey}`, { w: 3.5 });
    } else if (eyes === 'half') {
      s += line(-ex - 5 + lx, ey, -ex + 5 + lx, ey, 3.5) + line(ex - 5 + lx, ey, ex + 5 + lx, ey, 3.5);
      s += path(`M${-ex - 4 + lx} ${ey} Q${-ex + lx} ${ey + 5} ${-ex + 4 + lx} ${ey}`, { w: 3 });
      s += path(`M${ex - 4 + lx} ${ey} Q${ex + lx} ${ey + 5} ${ex + 4 + lx} ${ey}`, { w: 3 });
    }
    // brows
    const b = e.brows || { lift: 0, tilt: 0 };
    const by = -12 + b.lift;
    const browL = { cx: -ex + lx, lift: b.raise === 'left' ? -5 : 0 };
    const browR = { cx: ex + lx, lift: b.raise === 'right' ? -5 : 0 };
    const tilt = b.tilt || 0; // degrees
    const half = 5.5;
    const dyIn = Math.sin(rad(tilt)) * half;
    // left brow: inner end is the right end
    s += line(browL.cx - half, by + browL.lift + dyIn, browL.cx + half, by + browL.lift - dyIn, 3.5);
    s += line(browR.cx - half, by + browR.lift - dyIn, browR.cx + half, by + browR.lift + dyIn, 3.5);
    // mouth
    const mx = lx * 0.6, my = 12 + ly * 0.4;
    const m = talkOpen != null ? 'talk' : e.mouth;
    switch (m) {
      case 'smile': s += path(`M${mx - 8} ${my - 1} Q${mx} ${my + 7} ${mx + 8} ${my - 1}`, { w: 4 }); break;
      case 'grin': s += fillOnly(`M${mx - 10} ${my - 2} Q${mx} ${my + 13} ${mx + 10} ${my - 2} Z`, C.ink); break;
      case 'o': s += ellipse(mx, my + 2, 5, 7); break;
      case 'frown': s += path(`M${mx - 8} ${my + 5} Q${mx} ${my - 2} ${mx + 8} ${my + 5}`, { w: 4 }); break;
      case 'flat': s += line(mx - 7, my + 2, mx + 7, my + 2, 4); break;
      case 'side': s += line(mx - 3, my + 2, mx + 9, my, 4); break;
      case 'smirk': s += path(`M${mx - 7} ${my + 2} Q${mx + 2} ${my + 4} ${mx + 9} ${my - 2}`, { w: 4 }); break;
      case 'wavy': s += path(`M${mx - 9} ${my + 2} q3 -3 6 0 q3 3 6 0 q3 -3 6 0`, { w: 3.5 }); break;
      case 'smallO': s += ellipse(mx, my + 2, 3, 4); break;
      case 'talk': {
        const o = talkOpen;
        s += ellipse(mx, my + 1 + o * 2, 5 + o * 1.5, 1.5 + o * 6);
        break;
      }
    }
    return s;
  }

  /* Hair styles (head-local). 'tuft' is Scribble's own; others are for extra characters. */
  const HAIR = {
    tuft: path('M-6 -29 Q-2 -40 8 -34', { w: 6 }),
    none: '',
    bun: dot(0, -36, 10) + path('M-6 -29 Q0 -33 6 -29', { w: 5 }),
    long: path('M-30 -4 Q-34 -39 0 -39 Q34 -39 30 -4 L33 26 Q26 31 22 22 L24 -6 Q20 -26 0 -27 Q-20 -26 -24 -6 L-22 22 Q-26 31 -33 26 Z', { fill: C.ink, w: 2 }),
    spiky: path('M-20 -22 L-16 -38 L-8 -27 L0 -42 L8 -27 L16 -38 L20 -22', { w: 5 }),
    bald: ''
  };

  /* ------------------------------------------------------------------ *
   * COSTUMES. Layers:
   *   back  — torso-local, behind everything (capes)
   *   body  — torso-local (origin shoulder 0,0; hip at 0,50), over torso line, under arms
   *   head  — head-local (centre 0,0, r 30), above head
   *   face  — head-local, above face (glasses)
   *   hideHair — replaces the hair tuft
   * ------------------------------------------------------------------ */
  const COSTUMES = {
    caveman: {
      hideHair: true,
      body:
        path('M-15 -3 L16 -3 L22 52 L14 46 L8 55 L0 47 L-8 55 L-14 46 L-22 52 Z', { fill: C.brown, w: 4 }) +
        ellipse(-6, 14, 4, 2.5, C.darkBrown) + ellipse(8, 28, 5, 3, C.darkBrown) + ellipse(-4, 38, 4, 2.5, C.darkBrown),
      head: path('M-27 -12 Q-30 -26 -22 -24 Q-22 -36 -10 -30 Q-4 -42 6 -32 Q16 -40 18 -26 Q30 -28 27 -12 Q14 -22 0 -20 Q-14 -22 -27 -12 Z', { fill: C.ink, w: 2 })
    },
    peasant: {
      hideHair: true,
      body: path('M-15 -3 L15 -3 L19 50 L-19 50 Z', { fill: '#A68A5B', w: 4 }) + line(-17, 30, 17, 30, 4),
      head: path('M-35 8 Q-37 -37 0 -39 Q37 -37 35 8 Q29 -26 0 -27 Q-29 -26 -35 8 Z', { fill: '#8B6F47', w: 4 })
    },
    knight: {
      hideHair: true,
      body: path('M-15 -3 L15 -3 L17 52 L-17 52 Z', { fill: '#E8E2D5', w: 4 }) + line(0, 8, 0, 40, 6, C.red) + line(-10, 20, 10, 20, 6, C.red),
      head:
        path('M-33 -2 Q-34 -41 0 -42 Q34 -41 33 -2 L26 -2 Q24 -27 0 -28 Q-24 -27 -26 -2 Z', { fill: '#B8BCC2', w: 4 }) +
        path('M-3 -28 L-3 2 L3 2 L3 -28 Z', { fill: '#B8BCC2', w: 3 }) +
        path('M0 -42 Q10 -60 28 -55', { stroke: C.red, w: 6 })
    },
    egyptian: {
      hideHair: true,
      body:
        path('M-16 -2 Q0 16 16 -2 Q0 24 -16 -2 Z', { fill: C.blue, w: 3 }) +
        path('M-13 38 L13 38 L19 58 L-19 58 Z', { fill: '#F2EBDD', w: 4 }),
      head:
        path('M-33 -4 Q-34 -39 0 -41 Q34 -39 33 -4 L40 34 L28 34 L24 2 Q20 -25 0 -27 Q-20 -25 -24 2 L-28 34 L-40 34 Z', { fill: C.ochre, w: 4 }) +
        path('M-30 -20 Q0 -36 30 -20', { stroke: C.blue, w: 4 }) +
        line(-37, 12, -26, 12, 4, C.blue) + line(26, 12, 37, 12, 4, C.blue) + line(-39, 24, -27, 24, 4, C.blue) + line(27, 24, 39, 24, 4, C.blue)
    },
    roman: {
      body: path('M-16 -3 L16 -3 L18 52 L-18 52 Z', { fill: '#F2EBDD', w: 4 }) + line(14, -3, -16, 40, 7, C.red),
      head:
        path('M-28 -14 Q-20 -31 0 -33 Q20 -31 28 -14', { stroke: C.green, w: 4 }) +
        ellipse(-22, -24, 5, 2.5, C.green) + ellipse(-12, -31, 5, 2.5, C.green) + ellipse(12, -31, 5, 2.5, C.green) + ellipse(22, -24, 5, 2.5, C.green)
    },
    scientist: {
      body:
        path('M-17 -3 L17 -3 L23 60 L-23 60 Z', { fill: C.white, w: 4 }) +
        poly([[-8, -3], [0, 16], [8, -3]], 3) + path('M9 22 L17 22 L17 30 L9 30 Z', { w: 3 }),
      face: circle(-10, -2, 8.5, { w: 3 }) + circle(10, -2, 8.5, { w: 3 }) + line(-1.5, -3, 1.5, -3, 3)
    },
    office: {
      body: path('M-15 -3 L15 -3 L17 50 L-17 50 Z', { fill: C.white, w: 4 }) + poly([[-11, -3], [0, 6], [11, -3]], 3) + path('M0 6 L-5 12 L0 40 L5 12 Z', { fill: C.blue, w: 3 })
    },
    king: {
      back: path('M-18 -4 Q-36 40 -32 82 L32 82 Q36 40 18 -4 Z', { fill: C.red, w: 4 }),
      body: path('M-16 -3 Q0 8 16 -3 L14 4 Q0 14 -14 4 Z', { fill: C.white, w: 3 }),
      head: path('M-22 -24 L-24 -49 L-12 -37 L0 -53 L12 -37 L24 -49 L22 -24 Z', { fill: C.ochre, w: 4 })
    },
    explorer: {
      hideHair: true,
      body: line(-14, -2, 14, 44, 5, C.darkBrown) + path('M10 40 L24 40 L24 54 L10 54 Z', { fill: C.brown, w: 3 }),
      head:
        path('M-44 -18 Q0 -9 44 -18 Q0 -27 -44 -18 Z', { fill: '#C9B48A', w: 4 }) +
        path('M-24 -21 Q-22 -47 0 -47 Q22 -47 24 -21 Z', { fill: '#C9B48A', w: 4 }) +
        line(-23, -25, 23, -25, 4, C.darkBrown)
    },
    graduate: {
      head:
        path('M-36 -30 L0 -44 L36 -30 L0 -16 Z', { fill: C.ink, w: 3 }) +
        path('M-18 -24 L-18 -14 Q0 -6 18 -14 L18 -24', { fill: C.ink, w: 3 }) +
        path('M30 -30 L32 -10', { stroke: C.red, w: 3 })
    }
  };

  /* ------------------------------------------------------------------ *
   * PROPS. Each is fn(t) → svg string in local coords, base at (0,0),
   * drawn upward (negative y). Size ≈ 100 units unless noted.
   * ------------------------------------------------------------------ */
  const PROPS = {
    campfire: (t) => {
      const fl = 1 + 0.08 * Math.sin(t * 13) + 0.05 * Math.sin(t * 7.3);
      const sx = 1 + 0.04 * Math.sin(t * 9.1);
      return (
        g(path('M0 -6 C-30 -30 -14 -60 -4 -88 C2 -66 14 -64 12 -50 C24 -58 26 -74 22 -84 C40 -60 34 -24 0 -6 Z', { fill: C.red, w: 4 }) +
          fillOnly('M2 -12 C-14 -26 -6 -44 2 -60 C6 -46 14 -44 12 -34 C20 -40 22 -48 20 -54 C30 -36 22 -18 2 -12 Z', C.ochre),
          `translate(0 -4) scale(${f(sx)} ${f(fl)})`) +
        path('M-44 -2 L40 -20', { fill: 'none', w: 9, stroke: C.darkBrown }) +
        path('M-40 -20 L44 -2', { fill: 'none', w: 9, stroke: C.darkBrown }) +
        ellipse(-52, -2, 10, 6, C.paperDark) + ellipse(52, -2, 10, 6, C.paperDark)
      );
    },
    spear: () => line(0, 0, 0, -170, 5, C.darkBrown) + path('M0 -196 L-9 -168 L9 -168 Z', { fill: C.grey, w: 4 }),
    torch: (t) => {
      const fl = 1 + 0.1 * Math.sin(t * 12);
      return line(0, 0, 0, -70, 6, C.darkBrown) +
        g(path('M0 0 C-14 -10 -10 -26 0 -40 C10 -26 14 -10 0 0 Z', { fill: C.red, w: 3 }) + fillOnly('M0 -4 C-6 -10 -4 -18 0 -26 C4 -18 6 -10 0 -4 Z', C.ochre), `translate(0 -70) scale(1 ${f(fl)})`);
    },
    tree: (t) => {
      const sway = Math.sin(t * 1.3) * 1.5;
      return line(0, 0, 0, -90, 9) + line(0, -60, -18, -82, 6) + line(0, -70, 16, -92, 6) +
        g(path('M-52 -100 C-70 -130 -40 -170 -12 -160 C0 -200 50 -190 50 -150 C80 -140 72 -96 40 -98 C24 -82 -30 -80 -52 -100 Z', { fill: C.paperDark, w: 5 }), `rotate(${f(sway)} 0 -90)`);
    },
    hut: () =>
      path('M-70 0 L-70 -60 L70 -60 L70 0', { fill: C.paperDark, w: 5 }) +
      path('M-90 -56 L0 -130 L90 -56 Z', { fill: C.brown, w: 5 }) +
      line(-40, -80, -20, -98, 3) + line(10, -112, 30, -95, 3) + line(-10, -90, 10, -76, 3) +
      path('M-16 0 L-16 -38 Q0 -50 16 -38 L16 0', { fill: C.ink, w: 4 }),
    rock: () => path('M-50 0 C-56 -24 -34 -44 -6 -42 C22 -50 52 -30 50 0 Z', { fill: C.paperDark, w: 5 }) + line(-20, -26, -8, -30, 3),
    book: () =>
      path('M0 -10 C-20 -22 -44 -22 -60 -14 L-60 -74 C-44 -82 -20 -82 0 -70 Z', { fill: C.white, w: 4 }) +
      path('M0 -10 C20 -22 44 -22 60 -14 L60 -74 C44 -82 20 -82 0 -70 Z', { fill: C.white, w: 4 }) +
      line(-48, -56, -14, -60, 3) + line(-48, -44, -14, -48, 3) + line(14, -60, 48, -56, 3) + line(14, -48, 48, -44, 3),
    scroll: () =>
      path('M-40 -10 L40 -10 L40 -110 L-40 -110 Z', { fill: '#F2EBDD', w: 4 }) +
      path('M-48 -110 Q-48 -122 -40 -122 L48 -122 Q56 -122 56 -110 Q56 -100 48 -100', { fill: '#F2EBDD', w: 4 }) +
      line(-26, -90, 26, -90, 3) + line(-26, -74, 22, -74, 3) + line(-26, -58, 26, -58, 3) + line(-26, -42, 14, -42, 3),
    lightbulb: (t, o = {}) => {
      const on = o.on !== false;
      let s = '';
      if (on) for (let i = 0; i < 7; i++) {
        const a = -150 + i * 50, r1 = 52, r2 = 66 + 4 * Math.sin(t * 6 + i);
        const p1 = dir(a + 180, r1), p2 = dir(a + 180, r2);
        s += line(p1[0], -60 + p1[1], p2[0], -60 + p2[1], 4, C.ochre);
      }
      return s + path('M-14 -20 C-14 -30 -36 -42 -36 -66 C-36 -90 -18 -102 0 -102 C18 -102 36 -90 36 -66 C36 -42 14 -30 14 -20 Z', { fill: on ? C.ochre : C.white, w: 5 }) +
        path('M-14 -20 L14 -20 L14 -4 L-14 -4 Z', { fill: C.grey, w: 4 }) + line(-14, -12, 14, -12, 3);
    },
    question: () => path('M-30 -110 Q-30 -150 0 -150 Q32 -150 32 -118 Q32 -96 6 -86 L6 -56', { stroke: C.red, w: 14 }) + dot(6, -24, 9, C.red),
    exclaim: () => line(0, -150, 0, -60, 15, C.red) + dot(0, -24, 9, C.red),
    clock: (t) => {
      const m = dir(180 + t * 90, 34), h = dir(180 + t * 7.5, 22);
      return circle(0, -50, 48, { fill: C.white, w: 5 }) + line(0, -50, m[0], -50 + m[1], 4) + line(0, -50, h[0], -50 + h[1], 6) + dot(0, -50, 4) +
        line(0, -92, 0, -86, 3) + line(0, -14, 0, -8, 3) + line(-42, -50, -36, -50, 3) + line(36, -50, 42, -50, 3);
    },
    coin: () => circle(0, -30, 28, { fill: C.ochre, w: 5 }) + circle(0, -30, 18, { w: 3 }),
    phone: () => path('M-26 0 L26 0 L26 -100 L-26 -100 Z', { fill: C.ink, w: 5 }) + path('M-20 -14 L20 -14 L20 -88 L-20 -88 Z', { fill: '#DDE6EE', w: 2 }) + dot(0, -7, 3, C.white),
    sun: (t) => {
      let s = '';
      for (let i = 0; i < 10; i++) {
        const a = i * 36 + t * 12, p1 = dir(a, 46), p2 = dir(a, 64);
        s += line(p1[0], -70 + p1[1], p2[0], -70 + p2[1], 5, C.ochre);
      }
      return s + circle(0, -70, 36, { fill: C.ochre, w: 5 });
    },
    cloud: (t) => g(path('M-60 0 C-80 0 -80 -34 -56 -36 C-56 -66 -14 -72 -4 -48 C8 -70 50 -66 48 -36 C76 -36 76 0 52 0 Z', { fill: C.white, w: 5 }), `translate(${f(Math.sin(t * 0.6) * 6)} 0)`),
    arrow: () => path('M-60 0 Q0 -60 60 -10', { stroke: C.red, w: 8 }) + path('M40 -30 L62 -9 L34 -2', { stroke: C.red, w: 8 }),
    heart: (t) => g(path('M0 0 C-50 -34 -54 -80 -22 -84 C-8 -86 0 -74 0 -66 C0 -74 8 -86 22 -84 C54 -80 50 -34 0 0 Z', { fill: C.red, w: 4 }), `scale(${f(1 + 0.06 * Math.sin(t * 8))})`),
    pyramid: () => path('M-110 0 L0 -120 L110 0 Z', { fill: C.paperDark, w: 5 }) + line(0, -120, 30, 0, 3) + line(-60, -60, 26, -58, 2.5) + line(-36, -86, 14, -86, 2.5) + line(-84, -30, 46, -30, 2.5),
    castle: () =>
      path('M-90 0 L-90 -110 L-70 -110 L-70 -96 L-55 -96 L-55 -110 L-35 -110 L-35 -80 L35 -80 L35 -110 L55 -110 L55 -96 L70 -96 L70 -110 L90 -110 L90 0 Z', { fill: C.paperDark, w: 5 }) +
      path('M-18 0 L-18 -34 Q0 -54 18 -34 L18 0', { fill: C.ink, w: 4 }) + line(-62, -110, -62, -150, 3) + path('M-62 -150 L-36 -142 L-62 -134 Z', { fill: C.red, w: 3 }),
    house: () => path('M-60 0 L-60 -70 L60 -70 L60 0 Z', { fill: C.white, w: 5 }) + path('M-76 -66 L0 -126 L76 -66 Z', { fill: C.red, w: 5 }) +
      path('M-12 0 L-12 -40 L12 -40 L12 0', { fill: C.paperDark, w: 4 }) + path('M24 -56 L46 -56 L46 -36 L24 -36 Z', { fill: '#DDE6EE', w: 3 }),
    stool: () => path('M-30 -70 L30 -70 L30 -60 L-30 -60 Z', { fill: C.brown, w: 4 }) + line(-22, -60, -28, 0, 5) + line(22, -60, 28, 0, 5) + line(-24, -30, 24, -30, 4),
    sign: () => line(0, 0, 0, -90, 6, C.darkBrown) + path('M-50 -130 L50 -130 L50 -84 L-50 -84 Z', { fill: C.paperDark, w: 5 }),
    money: () => path('M-34 0 C-50 -20 -40 -60 -16 -70 L-10 -80 L10 -80 L16 -70 C40 -60 50 -20 34 0 Z', { fill: C.ochre, w: 5 }) + line(-12, -80, 12, -80, 5) + circle(0, -32, 10, { w: 3 }),
    globe: (t) => circle(0, -60, 54, { fill: '#DDE6EE', w: 5 }) +
      g(path('M-30 -90 C-10 -96 4 -80 -6 -66 C-16 -52 -34 -60 -40 -74 Z M10 -50 C24 -56 40 -44 34 -26 C24 -18 8 -26 10 -50 Z', { fill: C.green, w: 3 }), `translate(${f((t * 8) % 20 - 10)} 0)`) +
      line(0, -6, 0, 6, 6) + line(-30, 6, 30, 6, 6)
  };

  // how a held prop sits in the hand (prop units)
  const HOLD = {
    spear:     { s: 0.8, dx: 0, dy: 95, rot: 0 },
    torch:     { s: 0.85, dx: 0, dy: 30, rot: 0 },
    book:      { s: 0.42, dx: 0, dy: 10, rot: 0 },
    scroll:    { s: 0.42, dx: 0, dy: 20, rot: 0 },
    phone:     { s: 0.3, dx: 0, dy: 20, rot: 0 },
    lightbulb: { s: 0.4, dx: 0, dy: 10, rot: 0 },
    coin:      { s: 0.5, dx: 0, dy: 8, rot: 0 },
    money:     { s: 0.45, dx: 0, dy: 10, rot: 0 },
    heart:     { s: 0.35, dx: 0, dy: 10, rot: 0 },
    globe:     { s: 0.35, dx: 0, dy: 10, rot: 0 },
    clock:     { s: 0.4, dx: 0, dy: 10, rot: 0 }
  };

  /* ------------------------------------------------------------------ *
   * Character state → SVG (character-local coordinates)
   * ------------------------------------------------------------------ */
  function blendPose(a, b, k) {
    const o = {};
    for (const key of ['lean', 'head', 'jump']) o[key] = lerp(a[key] || 0, b[key] || 0, k);
    for (const key of ['aL', 'aR', 'lL', 'lR']) o[key] = [lerp(a[key][0], b[key][0], k), lerp(a[key][1], b[key][1], k)];
    return o;
  }
  const clonePose = (p) => blendPose(p, p, 0);

  const hipOf = (p) => -Math.max(
    RIG.thigh * Math.cos(rad(p.lL[0])) + RIG.shin * Math.cos(rad(p.lL[1])),
    RIG.thigh * Math.cos(rad(p.lR[0])) + RIG.shin * Math.cos(rad(p.lR[1]))) - (p.jump || 0);

  /**
   * state = { pose, expr, look, blink, talk(0..1|null), costume, hold, feet:'splay'|'forward', t, scarfSway }
   * returns svg string, origin at ground under hips, ~185 units tall
   */
  function drawCharacter(st) {
    const p = st.pose;
    const t = st.t || 0;
    const legDrop = (l) => RIG.thigh * Math.cos(rad(l[0])) + RIG.shin * Math.cos(rad(l[1]));
    const hipY = -Math.max(legDrop(p.lL), legDrop(p.lR)) - (p.jump || 0);
    const hip = [0, hipY];
    const lean = p.lean;
    const up = [Math.sin(rad(lean)), -Math.cos(rad(lean))];
    const sh = [hip[0] + up[0] * RIG.torso, hip[1] + up[1] * RIG.torso];
    const neckTop = [sh[0] + up[0] * RIG.neck, sh[1] + up[1] * RIG.neck];
    const ht = lean + p.head;
    const headC = [neckTop[0] + Math.sin(rad(ht)) * RIG.headR, neckTop[1] - Math.cos(rad(ht)) * RIG.headR];
    const cos = COSTUMES[st.costume] || null;

    const limb = (origin, ang, l1, l2, rel) => {
      const a1 = ang[0] + rel, a2 = ang[1] + rel;
      const d1 = dir(a1, l1), j = [origin[0] + d1[0], origin[1] + d1[1]];
      const d2 = dir(a2, l2), e = [j[0] + d2[0], j[1] + d2[1]];
      return { j, e, a2 };
    };
    const legL = limb(hip, p.lL, RIG.thigh, RIG.shin, 0);
    const legR = limb(hip, p.lR, RIG.thigh, RIG.shin, 0);
    const armL = limb(sh, p.aL, RIG.upperArm, RIG.foreArm, -lean);
    const armR = limb(sh, p.aR, RIG.upperArm, RIG.foreArm, -lean);
    const fwd = st.feet === 'forward';

    let s = '';
    // back costume layer
    if (cos && cos.back) s += g(cos.back, `translate(${f(sh[0])} ${f(sh[1])}) rotate(${f(lean)})`);
    // legs + feet
    s += poly([hip, legL.j, legL.e]) + line(legL.e[0], legL.e[1], legL.e[0] + (fwd ? RIG.foot : -RIG.foot), legL.e[1] + 1.5);
    s += poly([hip, legR.j, legR.e]) + line(legR.e[0], legR.e[1], legR.e[0] + RIG.foot, legR.e[1] + 1.5);
    // torso + neck
    s += line(hip[0], hip[1], neckTop[0], neckTop[1]);
    // body costume
    if (cos && cos.body) s += g(cos.body, `translate(${f(sh[0])} ${f(sh[1])}) rotate(${f(lean)})`);
    // head
    let head = circle(0, 0, RIG.headR, { fill: C.paper, w: SW });
    if (!(cos && cos.hideHair)) head += HAIR[st.hair || 'tuft'] || '';
    const e = EXPRESSIONS[st.expr] || EXPRESSIONS.neutral;
    const look = st.look || e.look || [0, 0];
    head += drawFace(e, look, st.blink, st.talk);
    if (cos && cos.face) head += cos.face;
    if (cos && cos.head) head += cos.head;
    s += g(head, `translate(${f(headC[0])} ${f(headC[1])}) rotate(${f(ht)})`);
    // scarf (signature) — knot + swinging tail
    const sway = (st.scarfSway || 0) + Math.sin(t * 2.6) * 2.5;
    if (st.scarf !== false) {
      const sc = typeof st.scarf === 'string' ? st.scarf : C.red;
      s += g(
        path('M-14 -6 Q0 5 14 -6', { stroke: sc, w: 10 }) +
          path(`M8 -1 Q${f(13 + sway * 0.4)} 10 ${f(15 + sway)} 22`, { stroke: sc, w: 8 }),
        `translate(${f(sh[0] + up[0] * 6)} ${f(sh[1] + up[1] * 6)}) rotate(${f(lean)})`
      );
    }
    // arms
    s += poly([sh, armL.j, armL.e]);
    s += poly([sh, armR.j, armR.e]);
    // held prop (right hand)
    if (st.hold && PROPS[st.hold]) {
      const h = HOLD[st.hold] || { s: 0.4, dx: 0, dy: 10, rot: 0 };
      s += g(g(PROPS[st.hold](t, st.holdOpts || {}), `scale(${h.s}) translate(${h.dx} ${h.dy}) rotate(${h.rot})`), `translate(${f(armR.e[0])} ${f(armR.e[1])})`);
    }
    return s;
  }

  /* ------------------------------------------------------------------ *
   * Tracks: numeric (eased segments) and discrete (switch at time)
   * ------------------------------------------------------------------ */
  class Track {
    constructor(v) { this.v0 = v; this.segs = []; }
    to(t0, dur, value, e = 'inOut') {
      this.segs.push({ t0, t1: t0 + Math.max(0, dur), to: value, e });
      this.segs.sort((a, b) => a.t0 - b.t0);
      return this;
    }
    at(t) {
      let v = this.v0;
      for (const s of this.segs) {
        if (t < s.t0) break;
        if (t >= s.t1) { v = s.to; continue; }
        return lerp(v, s.to, EASE[s.e]((t - s.t0) / (s.t1 - s.t0)));
      }
      return v;
    }
  }
  class Discrete {
    constructor(v) { this.v0 = v; this.keys = []; }
    set(t, v) { this.keys.push({ t, v }); this.keys.sort((a, b) => a.t - b.t); return this; }
    at(t) { let v = this.v0; for (const k of this.keys) { if (t < k.t) break; v = k.v; } return v; }
    lastChange(t) { let c = -1e9; for (const k of this.keys) { if (t < k.t) break; c = k.t; } return c; }
  }

  /* ------------------------------------------------------------------ *
   * Character (timeline object)
   * ------------------------------------------------------------------ */
  let charSeed = 0;
  class Character {
    constructor(scene, o = {}) {
      this.scene = scene;
      this.seed = (charSeed++ * 1.37) % 3;
      this.x = new Track(o.x || 0);
      this.y = new Track(o.y == null ? scene.ground : o.y);
      this.scale = new Track(o.scale || 2.2);
      this.opacity = new Track(o.opacity == null ? 1 : o.opacity);
      this.facing = new Discrete(o.facing || 1);
      this.exprT = new Discrete(o.expr || 'neutral');
      this.lookT = new Discrete(null);
      this.costumeT = new Discrete(o.costume || null);
      this.holdT = new Discrete(o.hold || null);
      this.poseKeys = [];
      this.initPose = clonePose(POSES[o.pose || 'idle']);
      this.walks = [];
      this.talks = [];
      this.waves = [];
      this.draw = null;
      this.autoBlink = o.blink !== false;
      this.scarf = o.scarf == null ? true : o.scarf;   // false = no scarf (extras), or a colour
      this.hair = o.hair || 'tuft';                    // tuft | bun | long | spiky | none
      this.anchor = o.anchor || 'ground';              // 'hip' keeps the hips at (x, y): use for lying/sitting in bed
      this.rot = new Track(o.rotate || 0);
    }
    /** Rotate the whole body around the hips (e.g. -90 = lying down, head to the left) */
    rotateTo(at, dur, deg, e = 'inOut') { this.rot.to(at, dur, deg, e); return this; }
    /** Move to a pose. at=start time, dur=blend time */
    pose(at, name, o = {}) {
      const base = typeof name === 'string' ? POSES[name] : name;
      if (!base) throw new Error('Scribble: unknown pose ' + name);
      this.poseKeys.push({ t: at, dur: o.dur == null ? 0.35 : o.dur, pose: o.tweak ? blendPose(base, Object.assign(clonePose(base), o.tweak), 1) : base });
      this.poseKeys.sort((a, b) => a.t - b.t);
      if (o.expr) this.expr(at, o.expr);
      return this;
    }
    expr(at, name) { this.exprT.set(at, name); return this; }
    look(at, xy) { this.lookT.set(at, xy); return this; }
    costume(at, name) { this.costumeT.set(at, name || null); return this; }
    hold(at, prop, opts) { this.holdT.set(at, prop ? { name: prop, opts: opts || {} } : null); return this; }
    face(at, dirn) { this.facing.set(at, dirn >= 0 ? 1 : -1); return this; }
    moveTo(at, dur, x, y, e = 'inOut') { this.x.to(at, dur, x, e); if (y != null) this.y.to(at, dur, y, e); return this; }
    scaleTo(at, dur, s, e = 'inOut') { this.scale.to(at, dur, s, e); return this; }
    fade(at, dur, op) { this.opacity.to(at, dur, op); return this; }
    /** Walk from current x to `to` between t0 and t1. */
    walk(t0, t1, to, o = {}) {
      const from = this.x.at(t0);
      this.x.to(t0, t1 - t0, to, 'linear');
      this.face(t0, to >= from ? 1 : -1);
      this.walks.push({ t0, t1, from, to, run: !!o.run, keepArms: !!o.keepArms });
      return this;
    }
    run(t0, t1, to) { return this.walk(t0, t1, to, { run: true }); }
    talk(t0, t1) { this.talks.push({ t0, t1 }); return this; }
    wave(t0, t1) { this.pose(t0, 'wave', { dur: 0.3 }); this.waves.push({ t0, t1 }); return this; }
    /** Ink "draws itself" between at and at+dur */
    drawOn(at, dur = 1.5) { this.draw = { t0: at, dur }; return this; }

    stateAt(t) {
      let pose = clonePose(this.initPose);
      for (const k of this.poseKeys) {
        if (t < k.t) break;
        const kk = k.dur <= 0 ? 1 : EASE.inOut(clamp((t - k.t) / k.dur));
        pose = blendPose(pose, k.pose, kk);
      }
      const sc = this.scale.at(t);
      let feet = 'splay', look = this.lookT.at(t), scarfSway = 0;
      // walking / running
      for (const w of this.walks) {
        if (t < w.t0 - 0.01 || t > w.t1 + 0.25) continue;
        const ww = windowW(t, w.t0 - 0.05, w.t1 + 0.2, 0.2);
        if (ww <= 0) continue;
        const speed = Math.abs(w.to - w.from) / Math.max(0.01, w.t1 - w.t0);
        const amp = w.run ? 38 : 24;
        const stride = 2 * 2 * 58 * Math.sin(rad(amp)) * sc;
        const ph = 2 * Math.PI * (speed / Math.max(1, stride)) * (clamp(t, w.t0, w.t1) - w.t0);
        const leg = (p0) => {
          const u = amp * Math.sin(p0);
          return [u, u - (w.run ? 55 : 30) * Math.max(0, Math.cos(p0))];
        };
        const armA = (p0, side) => {
          const u = side * 8 + (w.run ? 40 : 24) * Math.sin(p0);
          return [u, u + (w.run ? 70 : 20)];
        };
        const wp = {
          lean: w.run ? 14 : 3, head: w.run ? -6 : 0, jump: w.run ? 6 * Math.abs(Math.sin(ph)) : 0,
          lL: leg(ph), lR: leg(ph + Math.PI), aL: w.keepArms ? pose.aL : armA(ph + Math.PI, -1), aR: w.keepArms ? pose.aR : armA(ph, 1)
        };
        pose = blendPose(pose, wp, ww);
        if (ww > 0.5) feet = 'forward';
        if (!look) look = [4 * ww, 0];
        scarfSway = -6 * ww * (w.run ? 1.6 : 1) + Math.sin(ph * 2) * 2;
      }
      // waving forearm
      for (const w of this.waves) {
        const ww = windowW(t, w.t0, w.t1, 0.25);
        if (ww > 0) pose.aR[1] += 22 * Math.sin((t - w.t0) * Math.PI * 2 * 2.2) * ww;
      }
      // talking
      let talk = null;
      for (const tk of this.talks) {
        if (t >= tk.t0 && t <= tk.t1) {
          const k = t * 1.0 + this.seed;
          talk = clamp(Math.abs(Math.sin(k * 11)) * (0.55 + 0.45 * Math.abs(Math.sin(k * 3.7))));
          if (Math.sin(k * 1.9) > 0.92) talk *= 0.2; // little pauses
        }
      }
      const blink = this.autoBlink && ((t + this.seed) % 3.4) < 0.13;
      const h = this.holdT.at(t);
      // costume "poof" pulse
      const cc = this.costumeT.lastChange(t);
      const poof = t - cc < 0.35 ? Math.sin(((t - cc) / 0.35) * Math.PI) * 0.1 : 0;
      return {
        pose, expr: this.exprT.at(t), look, blink, talk, costume: this.costumeT.at(t),
        hold: h ? h.name : null, holdOpts: h ? h.opts : null, feet, t, scarfSway, scarf: this.scarf, hair: this.hair, rot: this.rot.at(t),
        x: this.x.at(t), y: this.y.at(t), scale: sc * (1 + poof), facing: this.facing.at(t), opacity: this.opacity.at(t)
      };
    }
    render(t) {
      const st = this.stateAt(t);
      if (st.opacity <= 0.001) return '';
      let drawStyle = '';
      if (this.draw) {
        const k = clamp((t - this.draw.t0) / this.draw.dur);
        if (k <= 0) return '';
        if (k < 1) drawStyle = ` class="sb-draw" style="--o:${f(1 - EASE.inOut(clamp(k / 0.8)))};--fo:${f(clamp((k - 0.55) / 0.45))}"`;
      }
      const body = drawCharacter(st);
      const hy = hipOf(st.pose);
      const inner = this.anchor === 'hip'
        ? `rotate(${f(st.rot)}) translate(0 ${f(-hy)})`
        : (st.rot ? `rotate(${f(st.rot)} 0 ${f(hy)})` : '');
      return g(body, `translate(${f(st.x)} ${f(st.y)}) scale(${f(st.scale * st.facing)} ${f(st.scale)}) ${inner}`, (st.opacity < 1 ? ` opacity="${f(st.opacity)}"` : '') + drawStyle);
    }
  }

  /* ------------------------------------------------------------------ *
   * Scene
   * ------------------------------------------------------------------ */
  let sceneCount = 0;
  const STYLE_ID = 'scribble-style';
  function injectStyle() {
    if (typeof document === 'undefined' || document.getElementById(STYLE_ID)) return;
    const st = document.createElement('style');
    st.id = STYLE_ID;
    st.textContent =
      '.sb-draw [pathLength]{stroke-dasharray:1 1;stroke-dashoffset:var(--o)}' +
      '.sb-draw .f{fill-opacity:var(--fo)}' +
      '.sb-stage{position:fixed;inset:0;width:100%;height:100%;display:block;background:' + C.paper + '}';
    document.head.appendChild(st);
  }

  class Scene {
    /**
     * container: element to fill (the SVG is created inside)
     * o.duration (s), o.ground (y of the floor, default 300),
     * o.fadeIn / o.fadeOut (s), o.groundLine (bool), o.wobble (bool), o.loop
     *
     * Coordinates: the SAFE AREA is the square x,y ∈ [-500, 500].
     * It is always fully visible on 16:9, 9:16, 1:1 or any ratio; the paper
     * simply extends past it on the longer side. Keep important things inside.
     */
    constructor(container, o = {}) {
      injectStyle();
      this.id = 'sb' + sceneCount++;
      this.duration = o.duration || 10;
      this.ground = o.ground == null ? 300 : o.ground;
      this.fadeIn = o.fadeIn == null ? 0.8 : o.fadeIn;
      this.fadeOut = o.fadeOut == null ? 0.8 : o.fadeOut;
      this.loop = o.loop !== false;
      this.groundLine = o.groundLine !== false;
      this.wobble = o.wobble === true; // subtle hand-drawn wobble; off by default because it slows recording
      this.chars = [];
      this.props = [];
      this.texts = [];
      this.customs = [];
      this.t = 0;
      this.playing = false;
      if (typeof document !== 'undefined' && container) this._mount(container);
    }
    _mount(container) {
      const NS = 'http://www.w3.org/2000/svg';
      const svg = document.createElementNS(NS, 'svg');
      svg.setAttribute('class', 'sb-stage');
      svg.setAttribute('role', 'img');
      svg.setAttribute('aria-label', 'Animated scene');
      svg.innerHTML =
        `<defs>` +
        `<filter id="${this.id}-wob" x="-5%" y="-5%" width="110%" height="110%"><feTurbulence type="fractalNoise" baseFrequency="0.035" numOctaves="1" seed="3" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="2.2"/></filter>` +
        `<radialGradient id="${this.id}-vig" cx="50%" cy="50%" r="75%"><stop offset="60%" stop-color="#000" stop-opacity="0"/><stop offset="100%" stop-color="#5a4a2a" stop-opacity="0.10"/></radialGradient>` +
        `</defs>` +
        `<g id="${this.id}-root"></g>` +
        `<rect id="${this.id}-vigr" fill="url(#${this.id}-vig)" pointer-events="none"/>`;
      // paper grain: one small tile rasterised once by the browser (cheap per frame)
      const tile = '<svg xmlns="http://www.w3.org/2000/svg" width="360" height="360"><filter id="n"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="3" stitchTiles="stitch"/><feColorMatrix values="0 0 0 0 0.45 0 0 0 0 0.38 0 0 0 0 0.25 0 0 0 0.10 0"/></filter><rect width="360" height="360" filter="url(#n)"/></svg>';
      svg.style.backgroundColor = C.paper;
      svg.style.backgroundImage = `url("data:image/svg+xml,${encodeURIComponent(tile)}")`;
      svg.style.backgroundSize = '360px 360px';
      container.appendChild(svg);
      this.svg = svg;
      this.root = svg.querySelector(`#${this.id}-root`);
      this.vig = svg.querySelector(`#${this.id}-vigr`);
      this._resize = () => this.fit();
      window.addEventListener('resize', this._resize);
      this.fit();
    }
    /** Fit the safe square into any viewport ratio (nothing is ever cut). */
    fit() {
      if (!this.svg) return;
      const r = this.svg.getBoundingClientRect();
      const W = r.width || window.innerWidth, H = r.height || window.innerHeight;
      const a = W / H, S = 1000;
      const vw = a >= 1 ? S * a : S, vh = a >= 1 ? S : S / a;
      this.view = { x: -vw / 2, y: -vh / 2, w: vw, h: vh };
      this.svg.setAttribute('viewBox', `${f(-vw / 2)} ${f(-vh / 2)} ${f(vw)} ${f(vh)}`);
      this.svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
      this.vig.setAttribute('x', f(-vw / 2)); this.vig.setAttribute('y', f(-vh / 2));
      this.vig.setAttribute('width', f(vw)); this.vig.setAttribute('height', f(vh));
      this.render(this.t);
    }
    character(o) { const c = new Character(this, o); this.chars.push(c); return c; }
    /**
     * Place a prop. o: {x, y, scale, at (draw start), draw (draw seconds, 0 = pop),
     * out (fade-out start), outDur, front (draw over characters), flip, opts}
     */
    prop(name, o = {}) {
      if (!PROPS[name]) throw new Error('Scribble: unknown prop ' + name);
      const p = Object.assign({ name, x: 0, y: this.ground, scale: 1, at: 0, draw: 0.8, out: null, outDur: 0.4, front: false, flip: false, opts: {} }, o);
      this.props.push(p);
      return p;
    }
    /**
     * Handwritten text. o: {x, y, size, at, until, style:'title'|'label'|'caption', color, write (seconds of write-on)}
     */
    text(str, o = {}) {
      const tx = Object.assign({ str, x: 0, y: -380, size: 64, at: 0, until: this.duration, color: C.ink, write: 0.6, weight: 700 }, o);
      this.texts.push(tx);
      return tx;
    }
    /** Add your own drawing: fn(t, scene) → svg string. layer: 'back' | 'front' */
    custom(fn, layer = 'back') { this.customs.push({ fn, layer }); return this; }

    _propSvg(p, t) {
      if (t < p.at) return '';
      let op = 1;
      if (p.out != null && t >= p.out) op = 1 - clamp((t - p.out) / p.outDur);
      if (op <= 0) return '';
      const k = p.draw > 0 ? clamp((t - p.at) / p.draw) : 1;
      const pop = p.draw > 0 ? 1 : EASE.back(clamp((t - p.at) / 0.3));
      const extra = (op < 1 ? ` opacity="${f(op)}"` : '') + (k < 1 ? ` class="sb-draw" style="--o:${f(1 - EASE.inOut(clamp(k / 0.85)))};--fo:${f(clamp((k - 0.5) / 0.5))}"` : '');
      return g(PROPS[p.name](t, p.opts), `translate(${f(p.x)} ${f(p.y)}) scale(${f(p.scale * pop * (p.flip ? -1 : 1))} ${f(p.scale * pop)})`, extra);
    }
    _textSvg(tx, i, t) {
      if (t < tx.at || t > tx.until) return '';
      const fin = clamp((t - tx.at) / 0.35), fout = clamp((tx.until - t) / 0.35);
      const op = Math.min(fin, fout);
      const k = tx.write > 0 ? EASE.out(clamp((t - tx.at) / tx.write)) : 1;
      const wEst = tx.str.length * tx.size * 0.55 + tx.size;
      const cid = `${this.id}-tc${i}`;
      const fam = `Caveat, 'Patrick Hand', 'Comic Sans MS', cursive`;
      return `<clipPath id="${cid}"><rect x="${f(tx.x - wEst / 2)}" y="${f(tx.y - tx.size * 1.2)}" width="${f(wEst * k)}" height="${f(tx.size * 1.8)}"/></clipPath>` +
        `<text x="${f(tx.x)}" y="${f(tx.y)}" text-anchor="middle" font-family="${fam}" font-size="${tx.size}" font-weight="${tx.weight}" fill="${tx.color}" opacity="${f(op)}" clip-path="url(#${cid})">${escapeXml(tx.str)}</text>`;
    }
    /** Render the frame at time t (seconds). Pure: same t → same frame. */
    render(t) {
      this.t = t;
      if (!this.root) return;
      const D = this.duration;
      let s = '';
      // ground line
      if (this.groundLine) {
        const k = clamp((t - 0.2) / 1.0);
        if (k > 0) {
          const vw = this.view ? this.view.w : 1778;
          s += `<g class="sb-draw" style="--o:${f(1 - EASE.inOut(k))};--fo:1">` + path(`M${f(-vw / 2 - 20)} ${this.ground + 4} Q0 ${this.ground - 2} ${f(vw / 2 + 20)} ${this.ground + 3}`, { w: 4, op: 0.55 }) + `</g>`;
        }
      }
      for (const c of this.customs) if (c.layer === 'back') s += c.fn(t, this);
      for (const p of this.props) if (!p.front) s += this._propSvg(p, t);
      for (const c of this.chars) s += c.render(t);
      for (const p of this.props) if (p.front) s += this._propSvg(p, t);
      for (const c of this.customs) if (c.layer === 'front') s += c.fn(t, this);
      this.texts.forEach((tx, i) => (s += this._textSvg(tx, i, t)));
      // global fade + soft scale in/out (professional open & close)
      const fi = this.fadeIn > 0 ? EASE.out(clamp(t / this.fadeIn)) : 1;
      const fo = this.fadeOut > 0 ? EASE.inOut(clamp((D - t) / this.fadeOut)) : 1;
      const op = Math.min(fi, fo);
      const sc = 0.94 + 0.06 * op;
      const wob = this.wobble ? ` filter="url(#${this.id}-wob)"` : '';
      this.root.setAttribute('opacity', f(op));
      this.root.setAttribute('transform', `scale(${f(sc)})`);
      this.root.innerHTML = `<g${wob}>${s}</g>`;
    }
    play() {
      if (this.playing || typeof requestAnimationFrame === 'undefined') return this;
      this.playing = true;
      let last = performance.now();
      const step = (now) => {
        if (!this.playing) return;
        const dt = (now - last) / 1000; last = now;
        let t = this.t + dt;
        if (t > this.duration) t = this.loop ? 0 : this.duration;
        this.render(t);
        requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
      return this;
    }
    pause() { this.playing = false; return this; }
    seek(t) { this.render(clamp(t, 0, this.duration)); return this; }
    /** For headless recording: window.__seek(t), window.__duration */
    exposeForRecording() {
      if (typeof window === 'undefined') return this;
      window.__duration = this.duration;
      window.__seek = (t) => { this.pause(); this.seek(t); };
      window.__scene = this;
      return this;
    }
  }

  function escapeXml(s) { return String(s).replace(/[<>&"']/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&#39;' }[c])); }

  /* ------------------------------------------------------------------ *
   * Static helpers (reference sheets, thumbnails)
   * ------------------------------------------------------------------ */
  function characterSVG(o = {}) {
    return drawCharacter({
      pose: clonePose(typeof o.pose === 'object' ? o.pose : POSES[o.pose || 'idle']),
      expr: o.expr || 'neutral', look: o.look, blink: false, talk: o.talk == null ? null : o.talk,
      costume: o.costume || null, hold: o.hold || null, holdOpts: o.holdOpts || {}, feet: o.feet || 'splay', t: o.t || 0,
      scarf: o.scarf == null ? true : o.scarf, hair: o.hair || 'tuft'
    });
  }
  function propSVG(name, t = 0, opts = {}) { return PROPS[name](t, opts); }

  const Scribble = {
    version: '1.1.0',
    palette: C,
    POSES, EXPRESSIONS, COSTUMES, PROPS, HOLD, HAIR, RIG, EASE,
    createScene: (container, o) => new Scene(container, o),
    characterSVG, propSVG,
    registerPose: (name, def) => { POSES[name] = def; },
    registerExpression: (name, def) => { EXPRESSIONS[name] = def; },
    registerCostume: (name, def) => { COSTUMES[name] = def; },
    registerProp: (name, fn, hold) => { PROPS[name] = fn; if (hold) HOLD[name] = hold; },
    svg: { line, poly, path, circle, dot, ellipse, g, fillOnly }
  };
  global.Scribble = Scribble;
  if (typeof module !== 'undefined' && module.exports) module.exports = Scribble;
})(typeof window !== 'undefined' ? window : globalThis);
