#!/usr/bin/env node
/**
 * MindBlip motion pack (lab, Nov 2026): render one animated graphic (number, compare or title)
 * as transparent PNG frames with GSAP in headless Chrome. Drop-in for pro._graphic_frames:
 * same frame size, same timing (count values are computed in Python so a count still lands
 * exactly on its spoken word), same file names (0000.png, 0001.png, ...).
 *
 *   node studio/gsapgfx/render.js spec.json out_dir
 *
 * spec: { kind, w, h, fps, frames, font, number: {...}, values: [...], land, compare: {...}, text }
 * Needs puppeteer-core and gsap (NODE_PATH) and Chrome (CHROME_PATH or /usr/bin/google-chrome).
 * Motion rules (HyperFrames): arrivals land on a long tail, overlap 30-50 %, words 60-120 ms apart,
 * a landed element holds dead still, blur only while something moves fast.
 */
const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer-core');

(async () => {
  const [specPath, outDir] = process.argv.slice(2);
  const spec = JSON.parse(fs.readFileSync(specPath, 'utf8'));
  fs.mkdirSync(outDir, { recursive: true });
  const gsapFile = require.resolve('gsap/dist/gsap.min.js');
  const page0 = fs.readFileSync(path.join(__dirname, 'page.html'), 'utf8')
    .replace('__GSAP__', fs.readFileSync(gsapFile, 'utf8'))
    .replace('__FONT__', 'file://' + path.resolve(spec.font));
  const html = path.join(outDir, '_page.html');
  fs.writeFileSync(html, page0);
  const exe = process.env.CHROME_PATH || '/usr/bin/google-chrome';
  const browser = await puppeteer.launch({ executablePath: exe, args: ['--no-sandbox', '--disable-gpu', '--allow-file-access-from-files', '--font-render-hinting=none'] });
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: spec.w, height: spec.h, deviceScaleFactor: 1 });
    await page.goto('file://' + path.resolve(html), { waitUntil: 'load' });
    await page.evaluate(async (s) => { await document.fonts.load('800 100px MB'); await document.fonts.ready; window.build(s); }, spec);
    await page.evaluate(() => document.fonts.ready);
    for (let i = 0; i < spec.frames; i++) {
      await page.evaluate((i) => window.seek(i), i);
      await page.screenshot({ path: path.join(outDir, String(i).padStart(4, '0') + '.png'), omitBackground: true });
    }
  } finally {
    await browser.close();
    fs.rmSync(html, { force: true });
  }
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
