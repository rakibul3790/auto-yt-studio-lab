#!/usr/bin/env node
/**
 * Fabelo Studio v2: quality control in a real Chrome, before anyone sees the film.
 *
 * For EVERY shot (start, middle, end), every transition (its midpoint), and the first and last
 * moments, at 16:9, 9:16 and 1:1:
 *   - saves a frame and a contact sheet per ratio (qc/sheet_16x9.png …) to look at
 *   - checks that no character, caption or title is partly cut off by the frame edge
 *     (fully off-screen is allowed: that is a camera choice; half a Scribble is a mistake)
 *   - checks the film fades in at the start and out at the end
 * With --video it also measures the delivery file: duration, size, loudness (-14 LUFS ±1), true peak (≤ -1 dBTP).
 *
 *   node v2/tools/qc.js work/<slug>/film.html work/<slug>/qc [--video work/<slug>/final.mp4] [--chrome /path]
 *
 * Writes qc/report.json and qc/report.md. Exit code 0 = pass, 2 = problems found (listed in the report).
 */
const path = require('path');
const fs = require('fs');
const { execFileSync, spawnSync } = require('child_process');

const argv = process.argv.slice(2);
const arg = (n, d) => { const i = argv.indexOf('--' + n); return i > -1 ? argv[i + 1] : d; };
const [pageArg, outDir] = argv.filter((a, i) => !a.startsWith('--') && !(argv[i - 1] || '').startsWith('--'));
if (!pageArg || !outDir) { console.log('usage: node qc.js film.html qcdir [--video final.mp4]'); process.exit(1); }
const RATIOS = { '16x9': [1280, 720], '9x16': [720, 1280], '1x1': [900, 900] };
const TOL = 3; // px

let puppeteer;
try { puppeteer = require('puppeteer'); } catch (e) { puppeteer = require('puppeteer-core'); }

function sheet(files, W, H, out) {
  if (!files.length) return;
  const cols = W < H ? Math.min(8, files.length) : Math.min(5, files.length);
  const rows = Math.ceil(files.length / cols);
  const w = Math.round(W / 3), h = Math.round(H / 3);
  const args = ['-y', '-v', 'error'];
  files.forEach((f) => args.push('-i', f));
  let fc = '', ins = '';
  for (let i = 0; i < rows * cols; i++) {
    fc += i < files.length ? `[${i}:v]scale=${w}:${h},drawbox=c=black@0.4:t=1[s${i}];` : `color=c=white:s=${w}x${h}:d=1[s${i}];`;
    ins += `[s${i}]`;
  }
  fc += `${ins}xstack=inputs=${rows * cols}:layout=${Array.from({ length: rows * cols }, (_, i) => `${(i % cols) * w}_${Math.floor(i / cols) * h}`).join('|')}`;
  args.push('-filter_complex', fc, '-frames:v', '1', out);
  try { execFileSync('ffmpeg', args); } catch (e) { console.error('contact sheet failed:', out); }
}

function measureVideo(file) {
  const pr = JSON.parse(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration,bit_rate:stream=codec_type,width,height,r_frame_rate,sample_rate,channels', '-of', 'json', file]).toString());
  const v = pr.streams.find((s) => s.codec_type === 'video') || {}, a = pr.streams.find((s) => s.codec_type === 'audio');
  const res = { duration_s: +(+pr.format.duration).toFixed(2), size: `${v.width}x${v.height}`, fps: v.r_frame_rate, mbps: +(pr.format.bit_rate / 1e6).toFixed(1), audio: null };
  if (a) {
    const err = String(spawnSync('ffmpeg', ['-hide_banner', '-nostats', '-i', file, '-vn', '-af', 'ebur128=peak=true', '-f', 'null', '-'], { encoding: 'utf8' }).stderr || '');
    const s = err.slice(err.lastIndexOf('Summary:'));
    const num = (re) => { const m = s.match(re); return m ? +m[1] : null; };
    res.audio = { sample_rate: +a.sample_rate, channels: a.channels, integrated_lufs: num(/I:\s+(-?[\d.]+) LUFS/), lra_lu: num(/LRA:\s+(-?[\d.]+) LU/), true_peak_dbtp: num(/Peak:\s+(-?[\d.]+) dBFS/) };
  }
  return res;
}

(async () => {
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await puppeteer.launch({ headless: 'new', protocolTimeout: 600000, executablePath: arg('chrome', process.env.CHROME_PATH || undefined), args: ['--no-sandbox', '--disable-dev-shm-usage', '--force-color-profile=srgb'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 720 });
  await page.goto('file://' + path.resolve(pageArg) + '?t=0', { waitUntil: 'load', timeout: 90000 });
  await page.evaluate(() => Promise.race([document.fonts ? document.fonts.ready : null, new Promise((r) => setTimeout(r, 5000))]));
  const info = await page.evaluate(() => ({ duration: window.__duration, cues: (window.__CUES && window.__CUES.cues) || [] }));
  if (!info.duration) throw new Error('page did not call film.ready()');
  const D = info.duration;
  const shots = info.cues.filter((c) => c.kind === 'shot');
  const trans = info.cues.filter((c) => c.kind === 'transition' && c.dur > 0);
  const times = new Map(); // t → label
  const add = (t, label, check = true) => { t = Math.max(0.02, Math.min(D - 0.02, +t.toFixed(2))); if (!times.has(t)) times.set(t, { label, check }); };
  for (const s of shots) {
    const a = s.at, b = s.end;
    add(a + Math.min(0.35, (b - a) / 4), `${s.name} start`); add((a + b) / 2, `${s.name} middle`); add(b - Math.min(0.35, (b - a) / 4), `${s.name} end`);
  }
  for (const c of trans) add(c.at, `${c.type} transition`, false);
  add(0.05, 'fade in', false); add(D - 0.05, 'fade out', false);
  // transitions dual-render two shots: skip the cut-off check inside them
  const inTransition = (t) => trans.some((c) => Math.abs(t - c.at) < c.dur / 2 + 0.02);
  const list = [...times.entries()].sort((x, y) => x[0] - y[0]);

  const problems = [], frames = {};
  for (const [r, [W, H]] of Object.entries(RATIOS)) {
    await page.setViewport({ width: W, height: H });
    fs.mkdirSync(path.join(outDir, r), { recursive: true });
    frames[r] = [];
    for (const [t, meta] of list) {
      const res = await page.evaluate((x, tol) => {
        window.__seek(x);
        const vw = innerWidth, vh = innerHeight, cut = [];
        document.querySelectorAll('[data-qc]').forEach((el) => {
          const b = el.getBoundingClientRect();
          if (b.width < 2 || b.height < 2) return;
          const op = parseFloat(getComputedStyle(el).opacity || '1');
          if (op < 0.05) return;
          const inside = b.left >= -tol && b.top >= -tol && b.right <= vw + tol && b.bottom <= vh + tol;
          const outside = b.right < 0 || b.bottom < 0 || b.left > vw || b.top > vh;
          if (!inside && !outside) cut.push({ kind: el.getAttribute('data-qc'), box: [b.left, b.top, b.right, b.bottom].map((v) => Math.round(v)) });
        });
        const root = document.querySelector('svg g[opacity]');
        return { cut, opacity: root ? parseFloat(root.getAttribute('opacity')) : 1 };
      }, t, TOL);
      const file = path.join(outDir, r, `${t.toFixed(2).padStart(6, '0')}.png`);
      await page.screenshot({ path: file });
      frames[r].push(file);
      if (meta.check && !inTransition(t) && res.cut.length) problems.push({ ratio: r, t, where: meta.label, cut: res.cut });
      if (meta.label === 'fade in' && res.opacity > 0.4) problems.push({ ratio: r, t, where: 'fade in', note: `opacity ${res.opacity} at the start (should fade in)` });
      if (meta.label === 'fade out' && res.opacity > 0.4) problems.push({ ratio: r, t, where: 'fade out', note: `opacity ${res.opacity} at the end (should fade out)` });
    }
    sheet(frames[r], W, H, path.join(outDir, `sheet_${r}.png`));
  }
  await browser.close();

  const report = { page: path.basename(pageArg), duration_s: D, shots: shots.length, transitions: trans.length, frames_checked: list.length * 3, problems };
  if (arg('video')) {
    report.video = measureVideo(arg('video'));
    const au = report.video.audio;
    if (!au) problems.push({ where: 'audio', note: 'no audio track' });
    else {
      if (au.integrated_lufs == null || Math.abs(au.integrated_lufs + 14) > 1) problems.push({ where: 'audio', note: `loudness ${au.integrated_lufs} LUFS (target -14 ±1)` });
      if (au.true_peak_dbtp == null || au.true_peak_dbtp > -0.9) problems.push({ where: 'audio', note: `true peak ${au.true_peak_dbtp} dBTP (limit -1)` });
    }
    if (Math.abs(report.video.duration_s - D) > 0.2) problems.push({ where: 'video', note: `file is ${report.video.duration_s}s, film is ${D}s` });
  }
  report.pass = problems.length === 0;
  fs.writeFileSync(path.join(outDir, 'report.json'), JSON.stringify(report, null, 1));
  const md = [`# QC: ${report.page}`, '', `Duration ${D}s · ${shots.length} shots · ${trans.length} transitions · ${report.frames_checked} frames checked at 16:9, 9:16, 1:1`, '',
    report.video ? `File: ${report.video.size}, ${report.video.fps} fps, ${report.video.mbps} Mb/s, ${report.video.duration_s}s` + (report.video.audio ? `, ${report.video.audio.integrated_lufs} LUFS, true peak ${report.video.audio.true_peak_dbtp} dBTP` : '') : '', '',
    report.pass ? '**PASS**: nothing cut off at any ratio; fades in and out; audio on target.' : `**${problems.length} problem(s):**`,
    ...problems.map((p) => `- ${p.ratio ? p.ratio + ' ' : ''}${p.t != null ? p.t + 's ' : ''}${p.where}: ${p.note || 'cut off: ' + p.cut.map((c) => c.kind + ' ' + c.box.join(',')).join('; ')}`)].join('\n');
  fs.writeFileSync(path.join(outDir, 'report.md'), md + '\n');
  console.log(md);
  process.exit(report.pass ? 0 : 2);
})().catch((e) => { console.error(e); process.exit(1); });
