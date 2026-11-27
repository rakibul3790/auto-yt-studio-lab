#!/usr/bin/env node
// Preview frames of a scene page: node shots.js page.html outdir "1,5,9.5" [--chrome path]
const path = require('path'), fs = require('fs');
const [page_, out, times] = process.argv.slice(2);
const ci = process.argv.indexOf('--chrome'), chrome = ci > -1 ? process.argv[ci + 1] : process.env.CHROME_PATH;
(async () => {
  let p; try { p = require('puppeteer'); } catch (e) { p = require('puppeteer-core'); }
  const b = await p.launch({ headless: 'new', executablePath: chrome, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  const pg = await b.newPage();
  fs.mkdirSync(out, { recursive: true });
  await pg.goto('file://' + path.resolve(page_) + '?t=0', { waitUntil: 'load' });
  await pg.evaluate(() => Promise.race([document.fonts ? document.fonts.ready : null, new Promise((r) => setTimeout(r, 5000))]));
  for (const [w, h, tag] of [[540, 960, 'v'], [1280, 720, 'h']]) {
    await pg.setViewport({ width: w, height: h });
    for (const t of times.split(',').map(Number)) {
      await pg.evaluate((t) => window.__seek(t), t);
      await pg.screenshot({ path: path.join(out, `${tag}_${String(t).padStart(5, '0')}.png`) });
    }
  }
  await b.close();
})().catch((e) => { console.error(e); process.exit(1); });
