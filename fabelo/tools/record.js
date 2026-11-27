#!/usr/bin/env node
/**
 * Record any Scribble scene page to MP4, frame by frame (exact timing).
 *
 *   npm i puppeteer            (or puppeteer-core + a Chrome path)
 *   node record.js demo.html out.mp4 --w 1920 --h 1080 --fps 30
 *   node record.js demo.html shorts.mp4 --w 1080 --h 1920   (9:16 works too)
 *   node record.js film.html part.mp4 --start 38.6 --end 131   (record only a time range)
 *
 * Needs ffmpeg on PATH. The page must call scene.exposeForRecording().
 */
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');

function arg(name, def) {
  const i = process.argv.indexOf('--' + name);
  return i > -1 ? process.argv[i + 1] : def;
}

(async () => {
  const [page_, out_] = process.argv.slice(2).filter((a, i, all) => !a.startsWith('--') && !(all[i - 1] || '').startsWith('--'));
  if (!page_ || !out_) {
    console.log('usage: node record.js <page.html> <out.mp4> [--w 1920 --h 1080 --fps 30 --chrome /path/to/chrome]');
    process.exit(1);
  }
  const W = +arg('w', 1920), H = +arg('h', 1080), FPS = +arg('fps', 30);
  let puppeteer;
  try { puppeteer = require('puppeteer'); } catch (e) { puppeteer = require('puppeteer-core'); }
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: arg('chrome', process.env.CHROME_PATH || undefined),
    args: ['--no-sandbox', '--disable-dev-shm-usage']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: W, height: H, deviceScaleFactor: 1 });
  const url = 'file://' + path.resolve(page_) + '?t=0';
  await page.goto(url, { waitUntil: 'load', timeout: 60000 });
  // wait for web fonts, but never more than 5 s (offline runs fall back to system fonts)
  await page.evaluate(() => Promise.race([document.fonts ? document.fonts.ready : null, new Promise((r) => setTimeout(r, 5000))]));
  const duration = await page.evaluate(() => window.__duration);
  if (!duration) throw new Error('Page did not call scene.exposeForRecording()');
  const T0 = +arg('start', 0), T1 = Math.min(duration, +arg('end', duration));
  const frames = Math.round((T1 - T0) * FPS);
  console.log(`Recording ${T0}s → ${T1}s @ ${FPS}fps = ${frames} frames, ${W}x${H}`);

  const ff = spawn('ffmpeg', ['-y', '-f', 'image2pipe', '-framerate', String(FPS), '-i', '-',
    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', out_], { stdio: ['pipe', 'inherit', 'inherit'] });

  for (let i = 0; i < frames; i++) {
    await page.evaluate((t) => window.__seek(t), T0 + i / FPS);
    const buf = await page.screenshot({ type: 'jpeg', quality: 92 }); // JPEG frames: ~6x faster than PNG
    if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
    if (i % FPS === 0) process.stdout.write(`\r${Math.round((i / frames) * 100)}%`);
  }
  ff.stdin.end();
  await new Promise((r) => ff.on('close', r));
  await browser.close();
  console.log('\nSaved', out_, fs.existsSync(out_) ? `(${(fs.statSync(out_).size / 1e6).toFixed(1)} MB)` : '');
})().catch((e) => { console.error(e); process.exit(1); });
