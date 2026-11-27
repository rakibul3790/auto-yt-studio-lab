#!/usr/bin/env node
/**
 * Fabelo Studio v2 — quick preview WITHOUT a browser.
 * Runs the scene script headless in Node, writes one SVG per frame and rasterises it with ffmpeg (librsvg).
 * Good for checking layout, camera framing and transitions at every ratio while you write the scene.
 * (Approximate: CSS draw-on, blend modes and blur look simpler than in Chrome. Final QC uses qc.js in Chrome.)
 *
 *   node v2/tools/preview.js work/<slug>/film.src.html work/<slug>/prev "1,4.2,7.5" [--ratios 9x16,16x9,1x1] [--timing voice/timing.json] [--sheet] [--cues cues.json]
 *   (times "-" with --cues only writes the cue sheet, e.g. to test the mix before recording)
 */
const fs = require('fs'), path = require('path'), vm = require('vm'), { execFileSync } = require('child_process');
const KIT = path.resolve(__dirname, '..', '..');
const argv = process.argv.slice(2);
const opt = (n, d) => { const i = argv.indexOf('--' + n); return i > -1 ? argv[i + 1] : d; };
const [src, outDir, times] = argv.filter((a, i) => !a.startsWith('--') && !(argv[i - 1] || '').startsWith('--'));
if (!src || !outDir || !times) { console.log('usage: node preview.js film.src.html outdir "t1,t2,…" [--ratios 9x16,16x9,1x1] [--timing timing.json] [--sheet]'); process.exit(1); }
const RATIOS = { '9x16': [540, 960], '16x9': [960, 540], '1x1': [720, 720] };
const ratios = opt('ratios', '9x16,16x9,1x1').split(',');
fs.mkdirSync(outDir, { recursive: true });

const html = fs.readFileSync(src, 'utf8');
const scripts = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)].map((m) => m[1]);
const ctx = { console, Math, JSON, URLSearchParams, location: { search: '' } };
ctx.window = ctx; ctx.globalThis = ctx;
ctx.document = { body: null, getElementById: () => true, fonts: null, createElement: () => { throw new Error('headless'); } };
const timingPath = opt('timing', null);
ctx.__TIMING = timingPath && fs.existsSync(timingPath) ? JSON.parse(fs.readFileSync(timingPath, 'utf8')) : null;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(KIT, 'lib', 'scribble.js'), 'utf8'), ctx);
vm.runInContext(fs.readFileSync(path.join(KIT, 'v2', 'lib', 'fabelo2.js'), 'utf8'), ctx);
for (const s of scripts) vm.runInContext(s.replace(/__TIMING_JSON__/g, 'null'), ctx);
const film = ctx.__FILM;
if (!film) { console.error('scene did not call film.ready()'); process.exit(1); }
if (opt('cues', null)) { fs.writeFileSync(opt('cues'), JSON.stringify(ctx.__CUES, null, 1)); console.log('cues →', opt('cues')); }
if (times === '-') { process.exit(0); }

const made = {};
for (const r of ratios) {
  const [W, H] = RATIOS[r];
  made[r] = [];
  for (const t of times.split(',').map(Number)) {
    const svg = film.svgFrame(t, W, H);
    const base = path.join(outDir, `${r}_${t.toFixed(2).padStart(6, '0')}`);
    fs.writeFileSync(base + '.svg', svg);
    execFileSync('ffmpeg', ['-y', '-v', 'error', '-i', base + '.svg', '-frames:v', '1', base + '.png']);
    fs.unlinkSync(base + '.svg');
    made[r].push(base + '.png');
  }
}
if (argv.includes('--sheet')) {
  for (const r of ratios) {
    const files = made[r]; if (!files.length) continue;
    const cols = r === '9x16' ? Math.min(6, files.length) : Math.min(4, files.length);
    const args = ['-y', '-v', 'error'];
    files.forEach((f) => args.push('-i', f));
    const rows = Math.ceil(files.length / cols);
    const [W, H] = RATIOS[r];
    let fc = '', ins = '';
    for (let i = 0; i < rows * cols; i++) {
      if (i < files.length) { fc += `[${i}:v]scale=${W / 2}:${H / 2},drawbox=c=black@0.5:t=1[s${i}];`; }
      else { fc += `color=c=white:s=${W / 2}x${H / 2}:d=1[s${i}];`; }
      ins += `[s${i}]`;
    }
    fc += `${ins}xstack=inputs=${rows * cols}:layout=${Array.from({ length: rows * cols }, (_, i) => `${(i % cols) * W / 2}_${Math.floor(i / cols) * H / 2}`).join('|')}`;
    args.push('-filter_complex', fc, '-frames:v', '1', path.join(outDir, `sheet_${r}.png`));
    try { execFileSync('ffmpeg', args); } catch (e) { console.error('sheet failed', r); }
  }
}
console.log('preview →', outDir);
