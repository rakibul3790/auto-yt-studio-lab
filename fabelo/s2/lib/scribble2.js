/* Scribble2 — the new smooth, thumbnail-style Scribble (separate from the main fabelo library).
   Approved look: front view "B" (2026-11-26). Head + scarf finish is locked from front.html.
   Everything is drawn in local units with (0,0) = ground point between the feet, then placed by
   draw({x, y, scale}).

   draw(opts):
     view   'front' | 'q' (3/4) | 'side' | 'back'
     f      1 = faces right, -1 = faces left (q/side)
     pose   { a1:[deg, bend, upperScale, foreScale], a2, l1:[deg, bend], l2, ft1, ft2 (foot tilt deg),
              lean, tilt (head), seat (hip height, sitting), lift (raise after grounding), hipDx }
            front/back: 1 = screen-left limb, 2 = screen-right, +deg = outward
            q/side:     1 = near limb,        2 = far limb,     +deg = forward
     face   neutral smile happy sad worried cry surprised angry focused sleepy closed
     look   [dx, dy] eye offset (-1..1)
     hands  [h1, h2]: relax | fist | open | point | phone
     phone  { ang, dx, dy } placement relative to the phone hand
     glow   phone glow on
     wind   0..1 scarf tails trail back (walk 0.3, run 0.8)
     scarf  false = no scarf (SIDE CHARACTERS ONLY; Scribble always wears it)
     over   [1] / [1,2] arms drawn on top of the head (hand-to-face poses)
     blink  true = eyes closed for this frame
     noHead true = body only (draw the head yourself with Scribble2.head, e.g. on a pillow)
   Scribble2.LAST after draw(): { phone:[x,y] | null, head:[x,y,r], hand:{1:[x,y],2:[x,y]} } in page coordinates (light layers, props in hands)
*/
(function () {
  const INK = '#151314', LINE = '#1B1817', EDGE = '#3B3737';
  const B = { r: 122, torsoL: 205, torsoW: 60, legW: 24, armW: 17.5, thigh: 155, shin: 151, upper: 104, fore: 96 };
  let uid = 0;
  const LAST = {};
  const rad = (d) => (d * Math.PI) / 180;
  const fx = (v) => (+v).toFixed(2);

  function defs() {
    return `<defs>
    <radialGradient id="s2head" cx="62%" cy="34%" r="72%"><stop offset="0%" stop-color="#FFFFFF"/><stop offset="60%" stop-color="#F8F6F1"/><stop offset="100%" stop-color="#E4E0D8"/></radialGradient>
    <linearGradient id="s2red" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#F45B4E"/><stop offset="100%" stop-color="#D83A30"/></linearGradient>
    <linearGradient id="s2tail" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#D9392F"/><stop offset="45%" stop-color="#F35749"/><stop offset="100%" stop-color="#C9312A"/></linearGradient>
    <linearGradient id="s2back" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#B92B24"/><stop offset="100%" stop-color="#9E231E"/></linearGradient>
    <linearGradient id="s2screen" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#E4F2FF"/><stop offset="100%" stop-color="#7FB4EE"/></linearGradient>
    <radialGradient id="s2glow"><stop offset="0%" stop-color="#9CCBFF" stop-opacity="0.75"/><stop offset="100%" stop-color="#9CCBFF" stop-opacity="0"/></radialGradient>
    <radialGradient id="s2faceglow"><stop offset="0%" stop-color="#A9D2FF" stop-opacity="0.55"/><stop offset="100%" stop-color="#A9D2FF" stop-opacity="0"/></radialGradient>
    <radialGradient id="s2tear" cx="40%" cy="35%" r="70%"><stop offset="0%" stop-color="#E8F6FF"/><stop offset="100%" stop-color="#5FA8E6"/></radialGradient>
    <filter id="s2b6" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="6"/></filter>
    <filter id="s2b10" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="10"/></filter>
    <filter id="s2b3"><feGaussianBlur stdDeviation="2.2"/></filter>
    </defs>`;
  }

  // ---------- geometry helpers ----------
  function bez(p, t) {
    const u = 1 - t;
    const x = u * u * u * p[0][0] + 3 * u * u * t * p[1][0] + 3 * u * t * t * p[2][0] + t * t * t * p[3][0];
    const y = u * u * u * p[0][1] + 3 * u * u * t * p[1][1] + 3 * u * t * t * p[2][1] + t * t * t * p[3][1];
    const dx = 3 * u * u * (p[1][0] - p[0][0]) + 6 * u * t * (p[2][0] - p[1][0]) + 3 * t * t * (p[3][0] - p[2][0]);
    const dy = 3 * u * u * (p[1][1] - p[0][1]) + 6 * u * t * (p[2][1] - p[1][1]) + 3 * t * t * (p[3][1] - p[2][1]);
    const l = Math.hypot(dx, dy) || 1;
    return { x, y, nx: -dy / l, ny: dx / l, tx: dx / l, ty: dy / l };
  }
  const seg = (a, b) => [a, [a[0] + (b[0] - a[0]) / 3, a[1] + (b[1] - a[1]) / 3], [a[0] + (2 * (b[0] - a[0])) / 3, a[1] + (2 * (b[1] - a[1])) / 3], b];
  function limb(p, wf, N = 24) {
    const L = [], R = [];
    for (let i = 0; i <= N; i++) {
      const t = i / N, q = bez(p, t), w = wf(t) / 2;
      L.push([q.x + q.nx * w, q.y + q.ny * w]); R.push([q.x - q.nx * w, q.y - q.ny * w]);
    }
    const f = (a) => fx(a[0]) + ' ' + fx(a[1]);
    // explicit semicircle caps (always convex)
    const cap = (q, w, sgn) => {
      const pts = [];
      for (let j = 1; j < 10; j++) {
        const ph = (j / 10) * Math.PI, c = Math.cos(ph) * sgn, sn = Math.sin(ph) * sgn;
        pts.push([q.x + q.nx * w * c + q.tx * w * sn, q.y + q.ny * w * c + q.ty * w * sn]);
      }
      return pts;
    };
    let d = 'M' + f(L[0]);
    for (let i = 1; i <= N; i++) d += ' L' + f(L[i]);
    for (const c of cap(bez(p, 1), wf(1) / 2, 1)) d += ' L' + f(c);
    for (let i = N; i >= 0; i--) d += ' L' + f(R[i]);
    for (const c of cap(bez(p, 0), wf(0) / 2, -1)) d += ' L' + f(c);
    return d + ' Z';
  }
  const dirv = (deg) => [Math.sin(rad(deg)), Math.cos(rad(deg))];     // 0 = straight down, +deg toward +x
  const rot = (p, deg, o = [0, 0]) => {
    const c = Math.cos(rad(deg)), s = Math.sin(rad(deg)), x = p[0] - o[0], y = p[1] - o[1];
    return [o[0] + x * c - y * s, o[1] + x * s + y * c];
  };

  // ---------- head ----------
  const FACE_X = {
    front: { eyes: [[-0.29, 1], [0.29, 1]], mx: 0, mw: 1 },
    back: { eyes: [], mx: 0, mw: 0 },
    q: { eyes: [[0.1, 1], [0.58, 0.78]], mx: 0.36, mw: 0.82 },
    side: { eyes: [[0.5, 0.8]], mx: 0.6, mw: 0.38 },
  };
  function head(cx, cy, r, o = {}) {
    const view = o.view || 'front', f = o.f || 1, face = o.face || 'neutral', look = o.look || [0, 0];
    const id = 's2h' + (++uid);
    let s = `<g transform="rotate(${fx((o.tilt || 0) * f)} ${fx(cx)} ${fx(cy + r)})">`;
    s += `<clipPath id="${id}"><circle cx="${fx(cx)}" cy="${fx(cy)}" r="${fx(r)}"/></clipPath>`;
    s += `<circle cx="${fx(cx)}" cy="${fx(cy)}" r="${fx(r)}" fill="url(#s2head)"/>`;
    s += `<g clip-path="url(#${id})"><path fill-rule="evenodd" fill="#BDB8AE" opacity="0.55" filter="url(#s2b6)"
          d="M${fx(cx - r * 1.3)} ${fx(cy - r * 1.3)} h${fx(r * 2.6)} v${fx(r * 2.6)} h${fx(-r * 2.6)} Z
             M${fx(cx + r * 1.1)} ${fx(cy - r * 0.09)} a${fx(r)} ${fx(r)} 0 1 0 ${fx(-r * 2)} 0 a${fx(r)} ${fx(r)} 0 1 0 ${fx(r * 2)} 0 Z"/>`;
    if (o.glow) s += `<ellipse cx="${fx(cx + f * r * 0.25)}" cy="${fx(cy + r * 0.85)}" rx="${fx(r * 1.05)}" ry="${fx(r * 0.85)}" fill="url(#s2faceglow)"/>`;
    s += `</g>`;
    s += `<circle cx="${fx(cx)}" cy="${fx(cy)}" r="${fx(r)}" fill="none" stroke="${LINE}" stroke-width="${fx(r * 0.062)}"/>`;
    const F = FACE_X[view];
    if (!F.eyes.length) return s + '</g>';
    const lw = r * 0.04, ey = cy + r * 0.2 + look[1] * r * 0.07, lx = look[0] * r * 0.07;
    const mx = cx + f * F.mx * r + lx * 0.6, my = cy + r * 0.56 + look[1] * r * 0.03, mw = r * 0.13 * F.mw;
    const line = (d) => `<path d="${d}" stroke="${INK}" stroke-width="${fx(lw)}" fill="none" stroke-linecap="round" stroke-linejoin="round"/>`;
    const big = face === 'surprised' ? 1.28 : 1;
    for (const [ex0, sc] of F.eyes) {
      const x = cx + f * ex0 * r + lx, erx = r * 0.075 * sc * big, ery = r * 0.115 * big;
      const k = Math.sign(mx - x) || f;            // direction toward the face centre (inner side)
      if (o.blink && face !== 'happy') s += line(`M${fx(x - erx * 1.15)} ${fx(ey + ery * 0.1)} Q${fx(x)} ${fx(ey + ery * 0.45)} ${fx(x + erx * 1.15)} ${fx(ey + ery * 0.1)}`);
      else if (face === 'happy') s += line(`M${fx(x - erx * 1.2)} ${fx(ey + ery * 0.2)} Q${fx(x)} ${fx(ey - ery * 1.1)} ${fx(x + erx * 1.2)} ${fx(ey + ery * 0.2)}`);
      else if (face === 'sleepy' || face === 'closed') s += line(`M${fx(x - erx * 1.2)} ${fx(ey)} Q${fx(x)} ${fx(ey + ery * 0.5)} ${fx(x + erx * 1.2)} ${fx(ey)}`);
      else {
        s += `<ellipse cx="${fx(x)}" cy="${fx(ey)}" rx="${fx(erx)}" ry="${fx(ery)}" fill="${INK}"/>`;
        s += `<circle cx="${fx(x + erx * 0.35)}" cy="${fx(ey - ery * 0.45)}" r="${fx(r * 0.075 * 0.34 * big)}" fill="#FFF" opacity="0.95"/>`;
      }
      // brows
      const bw = r * 0.14 * sc, by = ey - r * 0.27 * (face === 'surprised' ? 1.25 : 1), xi = x + k * bw * 0.5, xo = x - k * bw * 0.5;
      if (face === 'sad' || face === 'worried' || face === 'cry') {
        const up = face === 'worried' ? 0.09 : 0.07;
        s += line(`M${fx(xi)} ${fx(by - r * up)} Q${fx(x)} ${fx(by - r * 0.035)} ${fx(xo)} ${fx(by + r * 0.025)}`);
      } else if (face === 'angry' || face === 'focused') {
        const dn = face === 'angry' ? 0.07 : 0.03;
        s += line(`M${fx(xi)} ${fx(by + r * dn)} L${fx(xo)} ${fx(by - r * dn * 0.6)}`);
      } else if (face === 'surprised' || face === 'happy') {
        s += line(`M${fx(x - bw * 0.5)} ${fx(by)} Q${fx(x)} ${fx(by - r * 0.06)} ${fx(x + bw * 0.5)} ${fx(by)}`);
      } else {
        s += line(`M${fx(x - bw * 0.5)} ${fx(by + r * 0.012)} Q${fx(x)} ${fx(by - r * 0.03)} ${fx(x + bw * 0.5)} ${fx(by + r * 0.012)}`);
      }
      if (face === 'cry' && ex0 === F.eyes[0][0]) {
        const tx = x - k * erx * 0.2, ty = ey + ery * 1.5, ts = r * 0.07;
        s += `<path d="M${fx(tx)} ${fx(ty - ts * 1.2)} C${fx(tx + ts * 0.7)} ${fx(ty - ts * 0.1)} ${fx(tx + ts * 0.75)} ${fx(ty + ts * 0.9)} ${fx(tx)} ${fx(ty + ts * 0.9)} C${fx(tx - ts * 0.75)} ${fx(ty + ts * 0.9)} ${fx(tx - ts * 0.7)} ${fx(ty - ts * 0.1)} ${fx(tx)} ${fx(ty - ts * 1.2)} Z" fill="url(#s2tear)" stroke="#2F6FA8" stroke-width="${fx(lw * 0.45)}"/>`;
      }
    }
    // mouth
    const M = (a, b) => line(`M${fx(mx - mw)} ${fx(my + a)} Q${fx(mx)} ${fx(my + b)} ${fx(mx + mw)} ${fx(my + a)}`);
    if (face === 'smile') s += M(0, r * 0.06);
    else if (face === 'happy') s += `<path d="M${fx(mx - mw * 1.25)} ${fx(my - r * 0.02)} Q${fx(mx)} ${fx(my + r * 0.15)} ${fx(mx + mw * 1.25)} ${fx(my - r * 0.02)} Z" fill="${INK}" stroke="${INK}" stroke-width="${fx(lw)}" stroke-linejoin="round"/>`;
    else if (face === 'sad' || face === 'cry' || face === 'closed') s += M(r * 0.03, -r * 0.06);
    else if (face === 'worried') s += line(`M${fx(mx - mw)} ${fx(my + r * 0.01)} q${fx(mw * 0.5)} ${fx(-r * 0.035)} ${fx(mw)} 0 t${fx(mw)} 0`);
    else if (face === 'surprised') s += `<ellipse cx="${fx(mx)}" cy="${fx(my + r * 0.02)}" rx="${fx(mw * 0.42)}" ry="${fx(r * 0.075)}" fill="${INK}"/>`;
    else if (face === 'angry') s += M(r * 0.03, -r * 0.03);
    else if (face === 'focused' || face === 'sleepy') s += line(`M${fx(mx - mw * 0.7)} ${fx(my)} L${fx(mx + mw * 0.7)} ${fx(my)}`);
    else s += M(0, r * 0.022);
    return s + '</g>';
  }

  // ---------- scarf ----------
  function ribbon(p, w0, w1, fill, edge, ew) {
    const N = 22, L = [], R = [];
    for (let i = 0; i <= N; i++) {
      const t = i / N, q = bez(p, t), w = (w0 + (w1 - w0) * t) / 2;
      L.push([q.x + q.nx * w, q.y + q.ny * w]); R.push([q.x - q.nx * w, q.y - q.ny * w]);
    }
    const f = (a) => fx(a[0]) + ' ' + fx(a[1]);
    let d = 'M' + f(L[0]);
    for (let i = 1; i <= N; i++) d += ' L' + f(L[i]);
    d += ' L' + f(R[N]);
    for (let i = N - 1; i >= 0; i--) d += ' L' + f(R[i]);
    let s = `<path d="${d} Z" fill="${fill}" stroke="${edge}" stroke-width="${fx(ew)}" stroke-linejoin="round"/>`;
    // highlight + fold
    let hl = '', fd = '';
    for (let i = 1; i <= 18; i++) {
      const t = 0.06 + (i / 18) * 0.86, q = bez(p, t), w = (w0 + (w1 - w0) * t) / 2;
      hl += (i > 1 ? ' L' : 'M') + fx(q.x + q.nx * w * 0.25) + ' ' + fx(q.y + q.ny * w * 0.25);
      fd += (i > 1 ? ' L' : 'M') + fx(q.x - q.nx * w * 0.45) + ' ' + fx(q.y - q.ny * w * 0.45);
    }
    s += `<path d="${hl}" stroke="#FF8A7C" stroke-width="${fx(w0 * 0.12)}" fill="none" opacity="0.45" stroke-linecap="round" filter="url(#s2b3)"/>`;
    s += `<path d="${fd}" stroke="#A9271F" stroke-width="${fx(w0 * 0.1)}" fill="none" opacity="0.35" stroke-linecap="round" filter="url(#s2b3)"/>`;
    // fringe at the end
    const e = bez(p, 1), n = 6;
    for (let i = 0; i < n; i++) {
      const u = -0.5 + i / (n - 1), bx = e.x + e.nx * w1 * u, by = e.y + e.ny * w1 * u;
      s += `<path d="M${fx(bx + e.tx * ew)} ${fx(by + e.ty * ew)} L${fx(bx + e.tx * w1 * 0.36)} ${fx(by + e.ty * w1 * 0.36)}" stroke="#7E1A15" stroke-width="${fx(w1 * 0.075)}" stroke-linecap="round"/>`;
    }
    return s;
  }
  function roll(nx, y, ww, hh, tilt, edge, ew) {
    let p = `<path d="M${fx(nx - ww * 0.5)} ${fx(y - hh * 0.1 - tilt)} Q${fx(nx - ww * 0.52)} ${fx(y - hh * 0.55 - tilt)} ${fx(nx - ww * 0.38)} ${fx(y - hh * 0.5 - tilt * 0.6)}
       Q${fx(nx)} ${fx(y - hh * 0.05)} ${fx(nx + ww * 0.38)} ${fx(y - hh * 0.5 + tilt * 0.6)} Q${fx(nx + ww * 0.52)} ${fx(y - hh * 0.55 + tilt)} ${fx(nx + ww * 0.5)} ${fx(y - hh * 0.1 + tilt)}
       Q${fx(nx + ww * 0.5)} ${fx(y + hh * 0.42 + tilt)} ${fx(nx + ww * 0.36)} ${fx(y + hh * 0.48 + tilt * 0.6)}
       Q${fx(nx)} ${fx(y + hh * 0.95)} ${fx(nx - ww * 0.36)} ${fx(y + hh * 0.48 - tilt * 0.6)} Q${fx(nx - ww * 0.5)} ${fx(y + hh * 0.42 - tilt)} ${fx(nx - ww * 0.5)} ${fx(y - hh * 0.1 - tilt)} Z"
       fill="url(#s2red)" stroke="${edge}" stroke-width="${fx(ew)}" stroke-linejoin="round"/>`;
    p += `<path d="M${fx(nx - ww * 0.33)} ${fx(y - hh * 0.22 - tilt * 0.5)} Q${fx(nx)} ${fx(y + hh * 0.18)} ${fx(nx + ww * 0.33)} ${fx(y - hh * 0.22 + tilt * 0.5)}" stroke="#FF8F80" stroke-width="${fx(hh * 0.13)}" fill="none" opacity="0.5" stroke-linecap="round" filter="url(#s2b3)"/>`;
    p += `<path d="M${fx(nx - ww * 0.28)} ${fx(y + hh * 0.38 - tilt * 0.4)} Q${fx(nx)} ${fx(y + hh * 0.66)} ${fx(nx + ww * 0.28)} ${fx(y + hh * 0.38 + tilt * 0.4)}" stroke="#A8271F" stroke-width="${fx(hh * 0.1)}" fill="none" opacity="0.4" filter="url(#s2b3)" stroke-linecap="round"/>`;
    return p;
  }
  // part: 'behind' (tail behind the body), 'front' (band + front tails), 'rolls'
  function scarf(part, nx, ny, w, o) {
    const view = o.view, f = o.f, wind = o.wind || 0, L = o.tail, ang = o.ang || 0;
    const h = w * 0.3, edge = '#9A2620', ew = w * 0.014, tw = w * 0.24;
    let s = '';
    const R = (pts) => pts.map((p) => rot(p, ang, [nx, ny]));
    const flutter = (x0, y0, len, back, droop) => {
      // tail trailing toward -f with wind
      const bx = -f * back, sway = Math.sin((o.phase || 0) * Math.PI * 2) * wind * len * 0.06;
      return R([[x0, y0], [x0 + bx * 0.25, y0 + len * 0.35 * droop], [x0 + bx * 0.75, y0 + len * 0.7 * droop + sway], [x0 + bx, y0 + len * droop - sway]]);
    };
    if (part === 'behind') {
      if (view === 'side' || view === 'q') {
        const x0 = nx - f * w * (view === 'side' ? 0.22 : 0.3), y0 = ny + h * 0.55;
        const back = w * 0.12 + wind * L * 0.85, droop = 1 - wind * 0.45;
        s += ribbon(flutter(x0, y0, L * 0.95, back, droop), tw * 0.95, tw * 1.05, 'url(#s2back)', edge, ew);
      }
      return s;
    }
    if (part === 'front') {
      if (view === 'front') {
        const g = (x, y) => rot([x, y], ang, [nx, ny]);
        const band = [[nx - w * 0.5, ny + h * 0.15], [nx, ny - h * 0.55], [nx + w * 0.5, ny + h * 0.15], [nx + w * 0.47, ny + h * 0.6], [nx, ny + h * 0.2], [nx - w * 0.47, ny + h * 0.6]].map((p) => g(p[0], p[1]));
        s += `<path d="M${fx(band[0][0])} ${fx(band[0][1])} Q${fx(band[1][0])} ${fx(band[1][1])} ${fx(band[2][0])} ${fx(band[2][1])} L${fx(band[3][0])} ${fx(band[3][1])} Q${fx(band[4][0])} ${fx(band[4][1])} ${fx(band[5][0])} ${fx(band[5][1])} Z" fill="url(#s2back)" stroke="${edge}" stroke-width="${fx(ew)}"/>`;
        const tx = nx + w * 0.25, ty = ny + h * 0.7;
        const sw = wind * L * 0.15;
        s += ribbon(R([[tx + tw * 0.5, ty - h * 0.1], [tx + tw * 0.55, ty + L * 0.3], [tx + tw * 0.8 + sw, ty + L * 0.55], [tx + tw * 0.95 + sw, ty + L * 0.8]]), tw * 0.9, tw * 0.95, 'url(#s2back)', edge, ew);
        s += ribbon(R([[tx, ty], [tx, ty + L * 0.35], [tx + tw * 0.08 + sw, ty + L * 0.7], [tx + tw * 0.12 + sw, ty + L]]), tw, tw * 1.08, 'url(#s2tail)', edge, ew);
      } else if (view === 'q') {
        const tx = nx + f * w * 0.12, ty = ny + h * 0.7, back = wind * L * 0.5;
        s += ribbon(flutter(tx, ty, L * 0.8, back - f * f * tw * 0.1, 1 - wind * 0.3), tw * 0.92, tw, 'url(#s2tail)', edge, ew);
      } else if (view === 'side') {
        const tx = nx + f * w * 0.16, ty = ny + h * 0.75, back = w * 0.02 + wind * L * 0.45;
        s += ribbon(flutter(tx, ty, L * 0.62, back, 1 - wind * 0.35), tw * 0.7, tw * 0.78, 'url(#s2tail)', edge, ew);
      }
      return s;
    }
    // rolls
    const ww = view === 'side' ? w * 0.62 : view === 'q' ? w * 0.86 : w;
    const tr = view === 'side' ? f * 8 : view === 'q' ? -f * 3 : 0;
    s += `<g transform="rotate(${fx(ang + tr)} ${fx(nx)} ${fx(ny)})">`;
    s += `<ellipse cx="${fx(nx)}" cy="${fx(ny + h * 1.25)}" rx="${fx(ww * 0.42)}" ry="${fx(h * 0.35)}" fill="#000" opacity="0.22" filter="url(#s2b6)"/>`;
    if (view === 'back') {
      s += roll(nx, ny + h * 0.62, ww * 0.98, h, 0, edge, ew);
      s += roll(nx, ny + h * 0.05, ww * 0.9, h * 0.92, 0, edge, ew);
    } else {
      s += roll(nx, ny + h * 0.62, ww * 0.98, h, h * 0.06 * (view === 'front' ? 1 : f), edge, ew);
      s += roll(nx, ny + h * 0.05, ww * 0.9, h * 0.92, -h * 0.05 * (view === 'front' ? 1 : f), edge, ew);
    }
    return s + '</g>';
  }

  // ---------- hands, shoes, phone ----------
  function hand(cx, cy, s, a, k, type) {
    let g = `<g transform="translate(${fx(cx)} ${fx(cy)}) rotate(${fx(a)})">`;
    const palm = (sx, sy) => `<path d="M${fx(-s * 0.3)} ${fx(-s * 0.95)} C${fx(-s * 0.34)} ${fx(-s * 0.62)} ${fx(-s * 0.6 * sx)} ${fx(-s * 0.42)} ${fx(-s * 0.58 * sx)} ${fx(-s * 0.05)} C${fx(-s * 0.6 * sx)} ${fx(s * 0.3 * sy)} ${fx(-s * 0.48 * sx)} ${fx(s * 0.78 * sy)} 0 ${fx(s * 0.8 * sy)} C${fx(s * 0.48 * sx)} ${fx(s * 0.78 * sy)} ${fx(s * 0.6 * sx)} ${fx(s * 0.3 * sy)} ${fx(s * 0.58 * sx)} ${fx(-s * 0.05)} C${fx(s * 0.6 * sx)} ${fx(-s * 0.42)} ${fx(s * 0.34)} ${fx(-s * 0.62)} ${fx(s * 0.3)} ${fx(-s * 0.95)} Z" fill="${INK}" stroke="${EDGE}" stroke-width="${fx(s * 0.05)}"/>`;
    const thumb = (spread) => `<path d="M${fx(-k * s * 0.38)} ${fx(-s * 0.2)} C${fx(-k * s * (0.78 + spread))} ${fx(-s * 0.05 - spread * s)} ${fx(-k * s * (0.8 + spread))} ${fx(s * 0.32 - spread * s * 0.6)} ${fx(-k * s * (0.56 + spread * 0.6))} ${fx(s * 0.42 - spread * s * 0.4)} C${fx(-k * s * 0.42)} ${fx(s * 0.48)} ${fx(-k * s * 0.3)} ${fx(s * 0.3)} ${fx(-k * s * 0.3)} ${fx(s * 0.15)} Z" fill="${INK}"/>`;
    if (type === 'fist') g += palm(0.95, 0.8) + thumb(-0.1);
    else if (type === 'open') g += palm(1.12, 1.12) + thumb(0.32);
    else if (type === 'point') g += palm(0.9, 0.78) + thumb(-0.05) + `<path d="M0 ${fx(s * 0.4)} L0 ${fx(s * 1.55)}" stroke="${INK}" stroke-width="${fx(s * 0.36)}" stroke-linecap="round"/>`;
    else g += palm(1, 1) + thumb(0);
    g += `<path d="M${fx(s * 0.18 * k)} ${fx(-s * 0.2)} Q${fx(s * 0.36 * k)} ${fx(s * 0.25)} ${fx(s * 0.12 * k)} ${fx(s * 0.6)}" stroke="#5A5656" stroke-width="${fx(s * 0.09)}" fill="none" stroke-linecap="round" opacity="0.4" filter="url(#s2b3)"/>`;
    return g + '</g>';
  }
  // front-ish shoe (toe points outward k) or profile shoe (toe points k). tilt rotates around the heel
  function shoe(ax, ay, L, k, mode, tilt = 0) {
    const gy = ay + L * 0.22;
    const X = (v) => ax + k * v;
    const len = mode === 'q' ? 0.88 : 1;
    const d = `M${fx(X(-L * 0.34))} ${fx(gy)} L${fx(X(L * 0.62 * len))} ${fx(gy)} C${fx(X(L * 0.86 * len))} ${fx(gy)} ${fx(X(L * 0.9 * len))} ${fx(gy - L * 0.2)} ${fx(X(L * 0.82 * len))} ${fx(gy - L * 0.3)}
      C${fx(X(L * 0.72 * len))} ${fx(gy - L * 0.44)} ${fx(X(L * 0.4))} ${fx(gy - L * 0.46)} ${fx(X(L * 0.16))} ${fx(gy - L * 0.5)}
      C${fx(X(-L * 0.06))} ${fx(gy - L * 0.6)} ${fx(X(-L * 0.3))} ${fx(gy - L * 0.58)} ${fx(X(-L * 0.38))} ${fx(gy - L * 0.4)}
      C${fx(X(-L * 0.48))} ${fx(gy - L * 0.2)} ${fx(X(-L * 0.5))} ${fx(gy)} ${fx(X(-L * 0.3))} ${fx(gy)} Z`;
    return `<g transform="rotate(${fx(-k * tilt)} ${fx(ax)} ${fx(ay)})"><path d="${d}" fill="${INK}" stroke="${EDGE}" stroke-width="${fx(L * 0.03)}"/>
      <path d="M${fx(X(L * 0.05))} ${fx(gy - L * 0.4)} Q${fx(X(L * 0.45))} ${fx(gy - L * 0.38)} ${fx(X(L * 0.7 * len))} ${fx(gy - L * 0.24)}" stroke="#6A6565" stroke-width="${fx(L * 0.07)}" fill="none" stroke-linecap="round" opacity="0.45" filter="url(#s2b3)"/>
      <path d="M${fx(X(-L * 0.3))} ${fx(gy - L * 0.06)} L${fx(X(L * 0.66 * len))} ${fx(gy - L * 0.06)}" stroke="#2C2828" stroke-width="${fx(L * 0.05)}" stroke-linecap="round" opacity="0.8"/></g>`;
  }
  function phone(cx, cy, ang, s, glow) {
    let g = '';
    if (glow) g += `<circle cx="${fx(cx)}" cy="${fx(cy)}" r="${fx(s * 2.2)}" fill="url(#s2glow)"/>`;
    g += `<g transform="translate(${fx(cx)} ${fx(cy)}) rotate(${fx(ang)})">
      <rect x="${fx(-s * 0.32)}" y="${fx(-s * 0.55)}" width="${fx(s * 0.64)}" height="${fx(s * 1.1)}" rx="${fx(s * 0.1)}" fill="#24272D" stroke="#0E0F12" stroke-width="${fx(s * 0.04)}"/>
      <rect x="${fx(-s * 0.26)}" y="${fx(-s * 0.48)}" width="${fx(s * 0.52)}" height="${fx(s * 0.96)}" rx="${fx(s * 0.06)}" fill="url(#s2screen)" opacity="${glow ? 1 : 0.85}"/>
      <path d="M${fx(-s * 0.2)} ${fx(-s * 0.4)} L${fx(s * 0.05)} ${fx(-s * 0.4)}" stroke="#FFFFFF" stroke-width="${fx(s * 0.05)}" opacity="0.7" stroke-linecap="round"/></g>`;
    return g;
  }

  // ---------- torso ----------
  function torsoPath(tw, hw, torsoL, skew = 0) {
    const shY = -torsoL, hipY = 0, wy = shY + torsoL * 0.62, ww = tw * 0.84, x = skew;
    return `M${fx(x)} ${fx(shY)} C${fx(x - tw * 0.6)} ${fx(shY)} ${fx(x - tw)} ${fx(shY + tw * 0.1)} ${fx(x - tw)} ${fx(shY + tw * 0.9)}
      C${fx(x - tw)} ${fx(shY + torsoL * 0.35)} ${fx(-ww)} ${fx(wy - torsoL * 0.15)} ${fx(-ww)} ${fx(wy)}
      C${fx(-ww)} ${fx(wy + torsoL * 0.18)} ${fx(-hw * 1.02)} ${fx(hipY - hw * 1.2)} ${fx(-hw * 1.02)} ${fx(hipY - hw * 0.45)}
      C${fx(-hw * 1.02)} ${fx(hipY + hw * 0.12)} ${fx(-hw * 0.62)} ${fx(hipY + hw * 0.28)} ${fx(-hw * 0.3)} ${fx(hipY + hw * 0.2)}
      Q${fx(-hw * 0.08)} ${fx(hipY + hw * 0.12)} 0 ${fx(hipY - hw * 0.12)}
      Q${fx(hw * 0.08)} ${fx(hipY + hw * 0.12)} ${fx(hw * 0.3)} ${fx(hipY + hw * 0.2)}
      C${fx(hw * 0.62)} ${fx(hipY + hw * 0.28)} ${fx(hw * 1.02)} ${fx(hipY + hw * 0.12)} ${fx(hw * 1.02)} ${fx(hipY - hw * 0.45)}
      C${fx(hw * 1.02)} ${fx(hipY - hw * 1.2)} ${fx(ww)} ${fx(wy + torsoL * 0.18)} ${fx(ww)} ${fx(wy)}
      C${fx(ww)} ${fx(wy - torsoL * 0.15)} ${fx(x + tw)} ${fx(shY + torsoL * 0.35)} ${fx(x + tw)} ${fx(shY + tw * 0.9)}
      C${fx(x + tw)} ${fx(shY + tw * 0.1)} ${fx(x + tw * 0.6)} ${fx(shY)} ${fx(x)} ${fx(shY)} Z`;
  }

  // ---------- the figure ----------
  function draw(o = {}) {
    const view = o.view || 'front', f = view === 'front' || view === 'back' ? 1 : o.f || 1;
    const P = Object.assign({ a1: [8, -3], a2: [8, -3], l1: [2.5, 0], l2: [2.5, 0], lean: 0, tilt: 0 }, o.pose || {});
    const hands = o.hands || ['relax', 'relax'];
    const { r, torsoL, torsoW, legW, armW, thigh, shin, upper, fore } = B;
    const isFront = view === 'front' || view === 'back';
    const wf = view === 'side' ? 0.74 : view === 'q' ? 0.9 : 1;
    const tw = (torsoW / 2) * wf, hw = legW * 1.12 * (view === 'side' ? 0.9 : view === 'q' ? 0.96 : 1);
    const footL = legW * 1.8;
    // limb screen angle
    const scr = (i, deg) => (isFront ? (i === 1 ? -deg : deg) : f * deg);
    // ---- legs (relative to hip centre at 0,0)
    const hipX = isFront ? [-hw * 0.5, hw * 0.5] : view === 'q' ? [-f * hw * 0.62, f * hw * 0.5] : [f * 2, -f * 2];
    const legs = [1, 2].map((i) => {
      const [deg, bend] = P['l' + i];
      const h = [hipX[i - 1], -hw * 0.6];
      const tS = scr(i, deg), sS = scr(i, deg - bend);
      const knee = [h[0] + dirv(tS)[0] * thigh, h[1] + dirv(tS)[1] * thigh];
      const ank = [knee[0] + dirv(sS)[0] * shin, knee[1] + dirv(sS)[1] * shin];
      return { i, h, knee, ank, tilt: P['ft' + i] || 0 };
    });
    // ---- ground the figure
    let hipY;
    if (P.seat != null) hipY = -P.seat;
    else hipY = -Math.max(...legs.map((L) => L.ank[1] + footL * 0.22));
    hipY += P.lift || 0;
    const hipX0 = P.hipDx || 0;
    const T = (p) => [p[0] + hipX0, p[1] + hipY];
    // ---- torso frame
    const lean = isFront ? P.lean : f * P.lean;
    const TR = (p) => T(rot(p, lean));
    const shTop = TR([0, -torsoL]);
    const shL = isFront ? [[-(tw - armW * 0.3), -torsoL + armW * 0.62], [tw - armW * 0.3, -torsoL + armW * 0.62]]
      : view === 'q' ? [[-f * (tw - armW * 0.25), -torsoL + armW * 0.62], [f * (tw - armW * 0.55), -torsoL + armW * 0.62]]
        : [[f * 1, -torsoL + armW * 0.7], [-f * 3, -torsoL + armW * 0.7]];
    const arms = [1, 2].map((i) => {
      const [deg, bend, us = 1, fs = 1] = P['a' + i];
      const sh = TR(shL[i - 1]);
      const uS = scr(i, deg), fS = scr(i, deg + bend);
      const el = [sh[0] + dirv(uS)[0] * upper * us, sh[1] + dirv(uS)[1] * upper * us];
      const wr = [el[0] + dirv(fS)[0] * fore * fs, el[1] + dirv(fS)[1] * fore * fs];
      return { i, sh, el, wr, fS };
    });
    const neck = TR([0, -torsoL - r * 0.12]);
    const headC = rot([neck[0], neck[1] - r * 0.9], lean, neck);
    const scarfN = TR([0, -torsoL - r * 0.1]);
    const sOpt = { view, f, wind: o.wind || 0, tail: torsoL * 0.72, ang: lean, phase: o.phase || 0 };
    const SC_ = o.scarf === false ? () => '' : scarf;
    // ---- painters
    const legW0 = (t) => legW * (1.12 - 0.15 * t), legW1 = (t) => legW * (0.97 - 0.15 * t);
    const armW0 = (t) => armW * (1.12 - 0.13 * t), armW1 = (t) => armW * (0.99 - 0.13 * t);
    // two-segment limb: outline layer first, then the fills on top, so the joint has no seam
    const pair = (d1, d2, outline) => (outline ? `<path d="${d1}" fill="none" stroke="${EDGE}" stroke-width="3.2"/><path d="${d2}" fill="none" stroke="${EDGE}" stroke-width="3.2"/>` : '')
      + `<path d="${d1}" fill="${INK}"/><path d="${d2}" fill="${INK}"/>`;
    const drawLeg = (L, near) => {
      const h = T(L.h), k = T(L.knee), a = T(L.ank);
      let s = pair(limb(seg(h, k), legW0), limb(seg(k, a), legW1), near && !isFront);
      const k2 = isFront ? (L.i === 1 ? -1 : 1) : f;
      s += shoe(a[0] + (isFront ? k2 * legW * 0.05 : f * legW * 0.1), a[1], footL, k2, view === 'q' ? 'q' : 'side', L.tilt);
      return s;
    };
    const handType = (i) => hands[i - 1] || 'relax';
    const drawArm = (A, near) => {
      let s = `<circle cx="${fx(A.sh[0])}" cy="${fx(A.sh[1])}" r="${fx(armW * 0.6)}" fill="${INK}"/>`;
      s += pair(limb(seg(A.sh, A.el), armW0), limb(seg(A.el, A.wr), armW1), true);
      const d = dirv(A.fS), hc = [A.wr[0] + d[0] * armW * 0.5, A.wr[1] + d[1] * armW * 0.5];
      LAST.hand = LAST.hand || {}; LAST.hand[A.i] = [(o.x || 0) + hc[0] * (o.scale || 1), (o.y || 0) + hc[1] * (o.scale || 1)];
      const k = isFront ? (A.i === 1 ? -1 : 1) : -f;
      if (handType(A.i) === 'phone' && o.phone) {
        const ph = o.phone, pc = [hc[0] + f * (ph.dx || 0), hc[1] + (ph.dy || -14)];
        s += phone(pc[0], pc[1], f * (ph.ang || 0), 44, o.glow);
        LAST.phone = [(o.x || 0) + pc[0] * (o.scale || 1), (o.y || 0) + pc[1] * (o.scale || 1)];
      }
      s += hand(hc[0], hc[1], armW * 1.3, -A.fS, k, handType(A.i) === 'phone' ? 'fist' : handType(A.i));
      return s;
    };
    const drawTorso = () => {
      let s = `<g transform="translate(${fx(T([0, 0])[0])} ${fx(T([0, 0])[1])}) rotate(${fx(lean)})">`;
      s += `<path d="${torsoPath(tw, hw, torsoL)}" fill="${INK}"/>`;
      const side = view === 'q' ? -f : view === 'side' ? -f : -1;
      s += `<path d="M${fx(side * tw * 0.62)} ${fx(-torsoL + tw * 1.4)} C${fx(side * tw * 0.66)} ${fx(-torsoL * 0.6)} ${fx(side * tw * 0.55)} ${fx(-torsoL * 0.38)} ${fx(side * hw * 0.62)} ${fx(-hw * 0.9)}" stroke="#5A5656" stroke-width="${fx(tw * 0.16)}" fill="none" stroke-linecap="round" opacity="0.38" filter="url(#s2b3)"/>`;
      s += `<rect x="${fx(-armW * 0.45)}" y="${fx(-torsoL - r * 0.26)}" width="${fx(armW * 0.9)}" height="${fx(r * 0.32)}" fill="${INK}"/>`;
      return s + '</g>';
    };
    // ---- compose
    let s = '';
    const sc = o.scale || 1;
    LAST.phone = null; LAST.head = [(o.x || 0) + headC[0] * sc, (o.y || 0) + headC[1] * sc, r * sc];
    s += `<g transform="translate(${fx(o.x || 0)} ${fx(o.y || 0)}) scale(${sc})">`;
    if (!o.noShadow) s += `<ellipse cx="${fx(hipX0)}" cy="3" rx="${fx(r * 0.85)}" ry="${fx(r * 0.08)}" fill="#3A2A18" opacity="0.16" filter="url(#s2b10)"/>`;
    const far = 2, near = 1, over = o.over || [];
    if (view === 'back') {
      s += drawLeg(legs[0], false) + drawLeg(legs[1], false);
      s += drawTorso();
      s += drawArm(arms[0], false) + drawArm(arms[1], false);
      s += SC_('rolls', scarfN[0], scarfN[1], r * 1.42, sOpt);
      if (!o.noHead) s += head(headC[0], headC[1], r, { view, f, tilt: P.tilt });
    } else if (isFront) {
      s += drawLeg(legs[0], false) + drawLeg(legs[1], false);
      s += drawTorso();
      s += SC_('front', scarfN[0], scarfN[1], r * 1.42, sOpt);
      for (const A of arms) if (!over.includes(A.i)) s += drawArm(A, true);
      s += SC_('rolls', scarfN[0], scarfN[1], r * 1.42, sOpt);
      if (!o.noHead) s += head(headC[0], headC[1], r, { view, f, face: o.face, look: o.look, tilt: P.tilt, glow: o.glow, blink: o.blink });
      for (const A of arms) if (over.includes(A.i)) s += drawArm(A, true);
    } else {
      s += SC_('behind', scarfN[0], scarfN[1], r * 1.42, sOpt);
      s += drawArm(arms[far - 1], false);
      s += drawLeg(legs[far - 1], false);
      s += drawLeg(legs[near - 1], true);
      s += drawTorso();
      s += SC_('front', scarfN[0], scarfN[1], r * 1.42, sOpt);
      if (!over.includes(1)) s += drawArm(arms[near - 1], true);
      s += SC_('rolls', scarfN[0], scarfN[1], r * 1.42, sOpt);
      if (!o.noHead) s += head(headC[0], headC[1], r, { view, f, face: o.face, look: o.look, tilt: P.tilt, glow: o.glow, blink: o.blink });
      if (over.includes(1)) s += drawArm(arms[near - 1], true);
    }
    return s + '</g>';
  }


  // A single arm (for characters mostly hidden: in bed under a blanket, behind a counter...).
  // o: { x, y } shoulder in page coords, deg (0 = down, + toward +x), bend, scale, hand ('relax'|'fist'|'open'|'point'|'phone'),
  //    k (thumb side: -1 / 1), phone: { ang, dx, dy }, glow, us/fs (segment scales). Sets LAST.phone when holding a phone.
  function arm(o) {
    const sc = o.scale || 1, { armW, upper, fore } = B;
    const uS = o.deg, fS = o.deg + (o.bend || 0);
    const sh = [0, 0], el = [dirv(uS)[0] * upper * (o.us || 1), dirv(uS)[1] * upper * (o.us || 1)];
    const wr = [el[0] + dirv(fS)[0] * fore * (o.fs || 1), el[1] + dirv(fS)[1] * fore * (o.fs || 1)];
    const w0 = (t) => armW * (1.12 - 0.13 * t), w1 = (t) => armW * (0.99 - 0.13 * t);
    let s = `<g transform="translate(${fx(o.x)} ${fx(o.y)}) scale(${sc})">`;
    const d1 = limb(seg(sh, el), w0), d2 = limb(seg(el, wr), w1);
    s += `<path d="${d1}" fill="none" stroke="${EDGE}" stroke-width="3.2"/><path d="${d2}" fill="none" stroke="${EDGE}" stroke-width="3.2"/>`;
    s += `<path d="${d1}" fill="${INK}"/><path d="${d2}" fill="${INK}"/>`;
    const d = dirv(fS), hc = [wr[0] + d[0] * armW * 0.5, wr[1] + d[1] * armW * 0.5];
    const type = o.hand || 'relax';
    if (type === 'phone') {
      const ph = o.phone || {}, pc = [hc[0] + (ph.dx || 0), hc[1] + (ph.dy == null ? -14 : ph.dy)];
      s += phone(pc[0], pc[1], ph.ang || 0, 44, o.glow);
      LAST.phone = [o.x + pc[0] * sc, o.y + pc[1] * sc];
    }
    s += hand(hc[0], hc[1], armW * 1.3, -fS, o.k || 1, type === 'phone' ? 'fist' : type);
    return s + '</g>';
  }

  // ---------- pose library ----------
  const POSES = {
    idleFront: { a1: [8, -3], a2: [8, -3], l1: [2.5, 0], l2: [2.5, 0] },
    idleQ: { a1: [-6, 6], a2: [9, 10], l1: [-3, 1], l2: [5, 2] },
    idleSide: { a1: [2, 8], a2: [-5, 6], l1: [2, 0], l2: [-2, 0] },
  };
  // walk cycle (side, facing right): 8 frames; frames 5-8 swap near/far
  const W4 = [
    { a1: [-22, 10], a2: [24, 16], l1: [26, 4], l2: [-20, 14], ft1: 16, ft2: -26 },          // contact: heel strike / toe-off
    { a1: [-12, 12], a2: [14, 16], l1: [14, 18], l2: [-14, 36], ft1: 0, ft2: -40, lift: 6 },  // down
    { a1: [0, 12], a2: [2, 14], l1: [0, 6], l2: [8, 56], ft1: 0, ft2: -28 },                   // passing
    { a1: [12, 12], a2: [-12, 12], l1: [-16, 2], l2: [24, 22], ft1: -12, ft2: 8, lift: -4 },  // up
  ];
  const swap = (p) => Object.assign({}, p, { a1: p.a2, a2: p.a1, l1: p.l2, l2: p.l1, ft1: p.ft2, ft2: p.ft1 });
  const WALK = W4.concat(W4.map(swap));
  const R4 = [
    { a1: [-38, 92], a2: [40, 88], l1: [30, 8], l2: [-30, 80], ft1: 12, ft2: -40, lean: 14 },
    { a1: [-14, 92], a2: [18, 90], l1: [6, 36], l2: [16, 108], ft1: 0, ft2: -35, lean: 14, lift: 4 },
    { a1: [36, 90], a2: [-36, 92], l1: [-34, 8], l2: [56, 84], ft1: -38, ft2: -10, lean: 15 },
    { a1: [42, 95], a2: [-42, 95], l1: [-26, 70], l2: [44, 34], ft1: -30, ft2: 10, lean: 15, lift: -30 },
  ];
  const RUN = R4.concat(R4.map(swap));

  window.Scribble2 = { draw, head, arm, defs, POSES, WALK, RUN, B, phone, LAST };
})();
