#!/usr/bin/env node
/**
 * Fabelo Studio v2: record a built film page to a master video, frame-exact, with real motion blur.
 *
 *   node v2/tools/record2.js work/<slug>/film.html work/<slug>/master.mp4 --w 1080 --h 1920 --fps 30
 *        [--blur 4] [--shutter 0.5] [--scale 2] [--workers 2] [--start 0 --end 44] [--png]
 *        [--cues work/<slug>/cues.json] [--chrome /path/to/chrome]
 *
 * Motion blur: each output frame is the average of --blur sub-frames spread over the shutter
 * (0.5 = a film camera's 180° shutter). Moving lines get a soft smear, still lines stay razor
 * sharp. Sub-frames never cross a hard cut, so cuts stay clean.
 *
 * 4K: --scale 2 renders at 2x pixel density with the SAME layout (1080x1920 page → 2160x3840 file).
 * Workers: the time range is split into parts that record in parallel, then joined losslessly.
 * --cues writes the film's cue sheet (cuts, shots, sfx cues) for mix.py and qc.js.
 *
 * Needs ffmpeg on PATH and puppeteer or puppeteer-core with a Chrome.
 * The master is near-lossless (x264 crf 8, 4:4:4); finish.py makes the delivery file.
 */
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn, execFileSync } = require('child_process');

const argv = process.argv.slice(2);
const arg = (n, d) => { const i = argv.indexOf('--' + n); return i > -1 ? argv[i + 1] : d; };
const flag = (n) => argv.includes('--' + n);
const BOOL = new Set(['--png']);
const [pageArg, outArg] = argv.filter((a, i) => !a.startsWith('--') && !((argv[i - 1] || '').startsWith('--') && !BOOL.has(argv[i - 1])));

if (!pageArg || !outArg) {
  console.log('usage: node record2.js film.html master.mp4 [--w 1080 --h 1920 --fps 30 --blur 4 --scale 1 --workers 2 --cues cues.json]');
  process.exit(1);
}
const W = +arg('w', 1080), H = +arg('h', 1920), FPS = +arg('fps', 30);
const BLUR = Math.max(1, Math.round(+arg('blur', 4)));
const SHUTTER = Math.min(1, Math.max(0, +arg('shutter', 0.5)));
const SCALE = Math.max(1, +arg('scale', 1));
const WORKERS = Math.max(1, Math.round(+arg('workers', Math.min(4, Math.max(1, os.cpus().length - 1)))));
const PNG = flag('png');

let puppeteer;
try { puppeteer = require('puppeteer'); } catch (e) { puppeteer = require('puppeteer-core'); }

async function openPage(browser) {
  const page = await browser.newPage();
  // the page lays out at W/SCALE x H/SCALE css px, drawn at SCALE device px per css px → W x H output
  await page.setViewport({ width: Math.round(W / SCALE), height: Math.round(H / SCALE), deviceScaleFactor: SCALE });
  await page.goto('file://' + path.resolve(pageArg) + '?t=0', { waitUntil: 'load', timeout: 90000 });
  await page.evaluate(() => Promise.race([document.fonts ? document.fonts.ready : null, new Promise((r) => setTimeout(r, 5000))]));
  return page;
}

/** sub-frame times for output frame i: spread over the shutter, kept on one side of any hard cut */
function subTimes(t, hardCuts, T1) {
  if (BLUR === 1 || SHUTTER === 0) return [t];
  const span = SHUTTER / FPS;
  let ts = Array.from({ length: BLUR }, (_, k) => t + (k / (BLUR - 1) - 0.5) * span);
  for (const c of hardCuts) {
    if (ts[0] < c && ts[ts.length - 1] >= c) {
      // keep every sub-frame on the same side of the cut as the frame itself
      ts = ts.map((x) => (t >= c ? Math.max(x, c) : Math.min(x, c - 1e-4)));
    }
  }
  return ts.map((x) => Math.min(Math.max(0, x), T1 - 1e-4));
}

async function recordPart(idx, f0, f1, T0, T1, hardCuts, tmp) {
  const browser = await launch();
  const page = await openPage(browser);
  const out = path.join(tmp, `part_${String(idx).padStart(2, '0')}.mkv`);
  const vf = BLUR > 1
    ? `tmix=frames=${BLUR},select='eq(mod(n\\,${BLUR})\\,${BLUR - 1})',setpts=N/(${FPS}*TB)`
    : 'null';
  const ff = spawn('ffmpeg', ['-y', '-v', 'error', '-f', 'image2pipe', '-framerate', String(FPS * BLUR), '-i', '-',
    '-vf', vf, '-r', String(FPS), '-c:v', 'libx264', '-preset', 'medium', '-crf', '8', '-pix_fmt', 'yuv444p', out],
  { stdio: ['pipe', 'inherit', 'inherit'] });
  const shot = PNG ? { type: 'png' } : { type: 'jpeg', quality: 95 };
  for (let i = f0; i < f1; i++) {
    for (const st of subTimes(T0 + i / FPS, hardCuts, T1)) {
      await page.evaluate((x) => window.__seek(x), st);
      const buf = await page.screenshot(shot);
      if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
    }
    progress[idx] = (i - f0 + 1) / (f1 - f0);
  }
  ff.stdin.end();
  await new Promise((r, j) => ff.on('close', (code) => (code ? j(new Error('ffmpeg failed on part ' + idx)) : r())));
  await browser.close();
  return out;
}

// one browser per worker: a background tab in a shared headless browser may never paint (screenshots hang)
const launch = () => puppeteer.launch({
  headless: 'new',
  protocolTimeout: 600000,
  executablePath: arg('chrome', process.env.CHROME_PATH || undefined),
  args: ['--no-sandbox', '--disable-dev-shm-usage', '--font-render-hinting=none', '--force-color-profile=srgb',
    '--disable-background-timer-throttling', '--disable-renderer-backgrounding', '--disable-backgrounding-occluded-windows']
});

const progress = [];
(async () => {
  const browser = await launch();
  const probe = await openPage(browser);
  const info = await probe.evaluate(() => ({ duration: window.__duration, cues: window.__CUES || null }));
  await browser.close();
  if (!info.duration) throw new Error('page did not call film.ready() / exposeForRecording()');
  if (arg('cues')) { fs.writeFileSync(arg('cues'), JSON.stringify(info.cues || {}, null, 1)); console.log('cues →', arg('cues')); }
  const hardCuts = ((info.cues && info.cues.cues) || []).filter((c) => c.kind === 'transition' && (c.type === 'cut' || c.type === 'smash')).map((c) => c.at);

  const T0 = +arg('start', 0), T1 = Math.min(info.duration, +arg('end', info.duration));
  const frames = Math.round((T1 - T0) * FPS);
  const parts = Math.min(WORKERS, Math.max(1, Math.floor(frames / FPS)));
  console.log(`recording ${T0}s → ${T1}s: ${frames} frames @ ${FPS} fps, ${W}x${H}, motion blur ${BLUR} sub-frames, ${parts} worker(s)`);
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'fabelo2-rec-'));
  const t0 = Date.now();
  const timer = setInterval(() => {
    const p = progress.reduce((a, b) => a + (b || 0), 0) / parts;
    const el = (Date.now() - t0) / 1000;
    process.stdout.write(`\r  ${(p * 100).toFixed(0)}%  ${el.toFixed(0)}s elapsed${p > 0.02 ? `, ~${((el / p) * (1 - p)).toFixed(0)}s left` : ''}   `);
  }, 2000);
  const jobs = [];
  for (let k = 0; k < parts; k++) {
    const f0 = Math.round((frames * k) / parts), f1 = Math.round((frames * (k + 1)) / parts);
    jobs.push(recordPart(k, f0, f1, T0, T1, hardCuts, tmp));
  }
  const files = await Promise.all(jobs);
  clearInterval(timer);

  const list = path.join(tmp, 'list.txt');
  fs.writeFileSync(list, files.map((f) => `file '${f}'`).join('\n'));
  execFileSync('ffmpeg', ['-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', list, '-c', 'copy', '-movflags', '+faststart', outArg]);
  for (const f of files) fs.unlinkSync(f);
  fs.unlinkSync(list); fs.rmdirSync(tmp);
  const sec = ((Date.now() - t0) / 1000).toFixed(0);
  console.log(`\nmaster → ${outArg} (${(fs.statSync(outArg).size / 1e6).toFixed(1)} MB, ${sec}s)`);
})().catch((e) => { console.error(e); process.exit(1); });
