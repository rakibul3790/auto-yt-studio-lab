/* Sets2 — scene helpers for Smooth Scribble (Scribble2) films.
   Timing helpers, pose blending, walk/run cycles, set pieces (room, bed, chair, table),
   night + phone light, word-by-word captions and handwritten titles.
   All set pieces take a "stage" { W, H, GY } so the same code works at 1920x1080 and 1080x1920.

   S2.lp(A, B, u)            blend two poses (numbers and arrays), u 0..1
   S2.walkAt(phase) / runAt  pose from the 8-key walk / run cycle (phase in cycles, keep x speed ≈ 460*scale px per walk cycle)
   S2.prog(t, a, b)          eased 0..1 between times a and b
   S2.blinkAt(t, offset)     true for ~0.1 s every 3.4 s
   S2.room(st, {night})      warm paper room: wall, floor, window, picture, plant
   S2.bed(x, st, sc, mirror) S2.chair(...) S2.table(...)   furniture in Scribble2 local units
   S2.night(alpha, light, st) blue night grade + phone glow from Scribble2.LAST (draw AFTER the figure)
   S2.caption(t, TIMING, st, {y, size, maxWords})          word-by-word, spoken word in red
   S2.title(text, x, y, size, {color, opacity, anchor})    handwritten (Caveat)
*/
(function () {
  const K = window.Scribble2;
  const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
  const lerp = (a, b, u) => a + (b - a) * u;
  const ease = (u) => { u = clamp(u); return u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2; };
  const prog = (t, a, b) => ease((t - a) / (b - a));
  const DEF = { a1: [8, -3], a2: [8, -3], l1: [2.5, 0], l2: [2.5, 0], lean: 0, tilt: 0, ft1: 0, ft2: 0, lift: 0 };
  function lp(A, B, u) {
    const o = {};
    for (const k of new Set([...Object.keys(A), ...Object.keys(B)])) {
      const a = A[k] !== undefined ? A[k] : DEF[k], b = B[k] !== undefined ? B[k] : DEF[k];
      if (Array.isArray(a)) o[k] = a.map((v, i) => lerp(v, b && b[i] !== undefined ? b[i] : v, u));
      else if (typeof a === 'number' && typeof b === 'number') o[k] = lerp(a, b, u);
      else o[k] = u < 0.5 ? a : b;
    }
    return o;
  }
  const cyc = (KEYS) => (ph) => { const n = KEYS.length, x = (((ph % 1) + 1) % 1) * n, k = Math.floor(x); return lp(KEYS[k], KEYS[(k + 1) % n], x - k); };
  const walkAt = cyc(K.WALK), runAt = cyc(K.RUN);
  const blinkAt = (t, off = 0) => ((t + off) % 3.4) < 0.11;
  let uid = 0;

  function room(st, o = {}) {
    const { W, H, GY } = st, night = !!o.night, id = (night ? 'skyN' : 'skyD') + (++uid);
    const u = Math.min(W, H) / 1080;                           // unit scale
    const wx = W * 0.1, wy = GY - 690 * u, ww = 300 * u, wh = 350 * u;
    let s = `<rect width="${W}" height="${H}" fill="#F6EDDB"/>`;
    s += `<radialGradient id="wl${id}" cx="17%" cy="35%" r="60%"><stop offset="0%" stop-color="#FFF8EA"/><stop offset="100%" stop-color="#F6EDDB" stop-opacity="0"/></radialGradient><rect width="${W}" height="${H}" fill="url(#wl${id})"/>`;
    s += `<rect y="${GY}" width="${W}" height="${H - GY}" fill="#E7D7BA"/><path d="M0 ${GY} L${W} ${GY}" stroke="#BFA984" stroke-width="${4 * u}"/>`;
    s += `<path d="M0 ${GY + 60 * u} L${W} ${GY + 60 * u} M0 ${GY + 130 * u} L${W} ${GY + 130 * u}" stroke="#D9C6A4" stroke-width="${2 * u}" opacity="0.6"/>`;
    s += night ? `<linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#18213D"/><stop offset="100%" stop-color="#2E3B63"/></linearGradient>`
      : `<linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#BFE0F4"/><stop offset="100%" stop-color="#EAF5FB"/></linearGradient>`;
    s += `<rect x="${wx}" y="${wy}" width="${ww}" height="${wh}" rx="${8 * u}" fill="url(#${id})"/>`;
    if (night) {
      s += `<circle cx="${wx + ww * 0.7}" cy="${wy + wh * 0.23}" r="${34 * u}" fill="#F4F1DE"/><circle cx="${wx + ww * 0.75}" cy="${wy + wh * 0.2}" r="${30 * u}" fill="url(#${id})"/>`;
      for (const [a, b] of [[0.17, 0.14], [0.37, 0.34], [0.23, 0.6], [0.83, 0.54], [0.53, 0.11], [0.9, 0.77]]) s += `<circle cx="${wx + ww * a}" cy="${wy + wh * b}" r="${2.4 * u}" fill="#F4F1DE" opacity="0.85"/>`;
    } else s += `<path d="M${wx + 40 * u} ${wy + 210 * u} q${30 * u} ${-25 * u} ${70 * u} ${-5 * u} q${30 * u} ${-23 * u} ${70 * u} ${3 * u} l0 ${12 * u} l${-140 * u} 0 Z" fill="#FFFFFF" opacity="0.9"/>`;
    s += `<rect x="${wx}" y="${wy}" width="${ww}" height="${wh}" rx="${8 * u}" fill="none" stroke="#2A231C" stroke-width="${7 * u}"/><path d="M${wx + ww / 2} ${wy + 4 * u} L${wx + ww / 2} ${wy + wh - 4 * u} M${wx + 4 * u} ${wy + wh / 2} L${wx + ww - 4 * u} ${wy + wh / 2}" stroke="#2A231C" stroke-width="${6 * u}"/>`;
    s += `<rect x="${wx - 20 * u}" y="${wy + wh}" width="${ww + 40 * u}" height="${18 * u}" rx="${6 * u}" fill="#D8C4A2" stroke="#2A231C" stroke-width="${4 * u}"/>`;
    const cl = (x0, dir) => `<path d="M${x0} ${wy - 20 * u} Q${x0 - dir * 10 * u} ${wy + wh * 0.55} ${x0 + dir * 15 * u} ${wy + wh + 40 * u} L${x0 + dir * 45 * u} ${wy + wh + 40 * u} Q${x0 + dir * 30 * u} ${wy + wh * 0.55} ${x0 + dir * 40 * u} ${wy - 20 * u} Z" fill="#E9DDC6" stroke="#2A231C" stroke-width="${3.5 * u}"/>`;
    s += cl(wx - 30 * u, 1) + cl(wx + ww + 30 * u, -1);
    s += `<path d="M${wx - 40 * u} ${wy - 20 * u} L${wx + ww + 40 * u} ${wy - 20 * u}" stroke="#2A231C" stroke-width="${6 * u}" stroke-linecap="round"/>`;
    if (o.picture !== false) {
      const px = W * 0.72, py = GY - 620 * u;
      s += `<rect x="${px}" y="${py}" width="${220 * u}" height="${160 * u}" rx="${6 * u}" fill="#FBF6EA" stroke="#2A231C" stroke-width="${6 * u}"/><path d="M${px + 20 * u} ${py + 140 * u} l${50 * u} ${-70 * u} l${40 * u} ${45 * u} l${35 * u} ${-35 * u} l${55 * u} ${60 * u} Z" fill="#9FB7A0" stroke="#2A231C" stroke-width="${3 * u}"/><circle cx="${px + 170 * u}" cy="${py + 40 * u}" r="${14 * u}" fill="#F2C46B"/>`;
    }
    if (o.plant !== false) {
      const cx = W * 0.91;
      s += `<path d="M${cx - 50 * u} ${GY} L${cx - 62 * u} ${GY - 120 * u} L${cx + 62 * u} ${GY - 120 * u} L${cx + 50 * u} ${GY} Z" fill="#C98F62" stroke="#2A231C" stroke-width="${4 * u}"/>`;
      for (const [a, l] of [[-40, 150], [-15, 190], [12, 175], [38, 140], [-60, 110], [60, 105]]) {
        const r = (a * Math.PI) / 180, x2 = cx + Math.sin(r) * l * u, y2 = GY - 120 * u - Math.cos(r) * l * u;
        s += `<path d="M${cx} ${GY - 120 * u} Q${cx + Math.sin(r) * l * 0.3 * u} ${GY - 120 * u - Math.cos(r) * l * 0.6 * u} ${x2} ${y2}" stroke="#2A231C" stroke-width="${3 * u}" fill="none"/>`;
        s += `<ellipse cx="${x2}" cy="${y2}" rx="${16 * u}" ry="${34 * u}" transform="rotate(${a} ${x2} ${y2})" fill="#7FA071" stroke="#2A231C" stroke-width="${3 * u}"/>`;
      }
    }
    return s;
  }
  // furniture in Scribble2 local units (same scale as the figure); mirror = true flips it
  const g = (x, st, sc, mirror, body) => `<g transform="translate(${x} ${st.GY}) scale(${mirror ? -sc : sc} ${sc})">${body}</g>`;
  const bed = (x, st, sc, mirror) => g(x, st, sc, mirror, `
    <rect x="-300" y="-150" width="380" height="150" rx="12" fill="#566684" stroke="#1E2433" stroke-width="4"/>
    <rect x="-302" y="-162" width="386" height="36" rx="16" fill="#8C9CB8" stroke="#1E2433" stroke-width="4"/>
    <path d="M-290 -150 Q-120 -120 60 -150 L66 -100 Q-120 -80 -296 -96 Z" fill="#6E7FA0" opacity="0.8"/>
    <rect x="-312" y="-330" width="26" height="330" rx="7" fill="#6B5240" stroke="#1E2433" stroke-width="4"/>
    <rect x="-285" y="-206" width="110" height="48" rx="20" fill="#E9E4D8" stroke="#1E2433" stroke-width="4"/>`);   // sit with pose.seat ≈ 166
  const chair = (x, st, sc, mirror) => g(x, st, sc, mirror, `
    <path d="M-78 -330 Q-84 -230 -74 -140" stroke="#3A332C" stroke-width="12" stroke-linecap="round" fill="none"/>
    <rect x="-92" y="-146" width="150" height="16" rx="6" fill="#5C4A3A" stroke="#2A221B" stroke-width="3"/>
    <path d="M-80 -130 L-84 0 M44 -130 L48 0" stroke="#3A332C" stroke-width="10" stroke-linecap="round"/>`);   // pose.seat ≈ 150
  const table = (x, st, sc, mirror) => g(x, st, sc, mirror, `
    <rect x="-160" y="-250" width="320" height="18" rx="6" fill="#E9E4D8" stroke="#1E2433" stroke-width="4"/>
    <path d="M-140 -232 L-140 0 M140 -232 L140 0" stroke="#3A332C" stroke-width="10" stroke-linecap="round"/>`);

  // night grade + phone light. Call AFTER drawing the figure (uses Scribble2.LAST).
  function night(alpha, light, st) {
    const { W, H } = st;
    let s = `<rect width="${W}" height="${H}" fill="#22305E" opacity="${alpha}" style="mix-blend-mode:multiply"/>`;
    s += `<rect width="${W}" height="${H}" fill="#0A0F24" opacity="${alpha * 0.22}"/>`;
    if (light && K.LAST.phone) {
      const [px, py] = K.LAST.phone, id = 'n' + (++uid);
      s += `<radialGradient id="p${id}"><stop offset="0%" stop-color="#A9D4FF" stop-opacity="${0.6 * light}"/><stop offset="100%" stop-color="#A9D4FF" stop-opacity="0"/></radialGradient>`;
      s += `<circle cx="${px}" cy="${py}" r="190" fill="url(#p${id})" style="mix-blend-mode:screen" opacity="0.6"/>`;
      const [hx, hy, hr] = K.LAST.head;
      s += `<clipPath id="h${id}"><circle cx="${hx}" cy="${hy}" r="${hr * 0.96}"/></clipPath>`;
      s += `<radialGradient id="f${id}"><stop offset="0%" stop-color="#CFE6FF" stop-opacity="${0.55 * light}"/><stop offset="100%" stop-color="#CFE6FF" stop-opacity="0"/></radialGradient>`;
      s += `<g clip-path="url(#h${id})"><ellipse cx="${hx - hr * 0.2}" cy="${hy + hr * 0.75}" rx="${hr * 1.2}" ry="${hr}" fill="url(#f${id})" style="mix-blend-mode:screen"/></g>`;
    }
    return s;
  }
  const FONT = "Caveat, 'Segoe Print', 'Comic Sans MS', cursive";
  function title(text, x, y, size, o = {}) {
    return `<text x="${x}" y="${y}" font-size="${size}" text-anchor="${o.anchor || 'start'}" fill="${o.color || '#1B1817'}" opacity="${o.opacity == null ? 1 : o.opacity}" font-family="${FONT}" font-weight="700">${text}</text>`;
  }
  // word-by-word caption: current line, spoken word red. TIMING = emo_voice timing.json
  function caption(t, TIMING, st, o = {}) {
    if (!TIMING) return '';
    const ln = TIMING.lines.find((l) => t >= l.start - 0.05 && t <= l.end + 0.35);
    if (!ln || !ln.words) return '';
    const max = o.maxWords || 6, words = ln.words;
    let k = words.findIndex((w) => t < w[2]); if (k < 0) k = words.length - 1;
    const page = Math.floor(k / max), shown = words.slice(page * max, page * max + max);
    const size = o.size || Math.round(Math.min(st.W, st.H) * (st.H > st.W ? 0.085 : 0.055)), y = o.y || st.H * 0.86;
    let s = `<text x="${st.W / 2}" y="${y}" font-size="${size}" text-anchor="middle" font-family="${FONT}" font-weight="700" paint-order="stroke" stroke="#FBF7EE" stroke-width="${size * 0.16}" stroke-linejoin="round">`;
    shown.forEach((w, i) => {
      const on = t >= w[1] && t < w[2] + 0.05, said = t >= w[1];
      s += `<tspan fill="${on ? '#E63946' : '#1B1817'}" fill-opacity="${said ? 1 : 0.45}">${w[0]}${i < shown.length - 1 ? ' ' : ''}</tspan>`;
    });
    return s + '</text>';
  }
  window.S2 = { clamp, lerp, ease, prog, lp, walkAt, runAt, blinkAt, room, bed, chair, table, night, title, caption, FONT };
})();
