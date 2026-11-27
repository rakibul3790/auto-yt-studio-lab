#!/usr/bin/env node
// Smooth Scribble (s2): contact sheet of chosen frames from a built film page.
//   node s2/tools/preview_s2.js work/<slug>/film.html work/<slug>/prev.png "1,3,5.5,8" [--w 1920 --h 1080 --cols 4] [--chrome PATH]
// The page must expose window.__seek(t). Look at every tile: arms hidden behind the head, feet under the floor,
// cut-off heads, phone glow and captions are the usual problems.
const path = require('path');
let pp; try { pp = require('puppeteer-core'); } catch (e) { pp = require('puppeteer'); }
const argv = process.argv.slice(2);
const arg = (n, d) => { const i = argv.indexOf('--' + n); return i > -1 ? argv[i + 1] : d; };
const [page_, out, ts] = argv.filter((a, i) => !a.startsWith('--') && !(argv[i - 1] || '').startsWith('--'));
(async () => {
  const W = +arg('w', 1920), H = +arg('h', 1080), cols = +arg('cols', 4);
  const times = ts.split(',').map(Number);
  const b = await pp.launch({ headless: 'new', executablePath: arg('chrome', process.env.CHROME_PATH) || undefined });
  const pg = await b.newPage();
  const errs = []; pg.on('pageerror', (e) => errs.push(String(e)));
  await pg.setViewport({ width: W, height: H });
  await pg.goto('file:///' + path.resolve(page_).split(path.sep).join('/'));
  await pg.evaluate(() => (document.fonts ? document.fonts.ready : null));
  const shots = [];
  for (const t of times) { await pg.evaluate((x) => window.__seek(x), t); shots.push((await pg.screenshot({ type: 'jpeg', quality: 80 })).toString('base64')); }
  const tw = W >= H ? 480 : 270, th = Math.round(tw * H / W), rows = Math.ceil(times.length / cols);
  const html = `<body style="margin:0;background:#222;display:grid;grid-template-columns:repeat(${cols},${tw}px);gap:4px">` +
    shots.map((s, i) => `<div style="position:relative"><img src="data:image/jpeg;base64,${s}" width="${tw}" height="${th}"><span style="position:absolute;left:6px;top:4px;color:#fff;background:#000a;font:14px sans-serif;padding:1px 4px">${times[i]}s</span></div>`).join('') + '</body>';
  await pg.setViewport({ width: cols * (tw + 4), height: rows * (th + 4) });
  await pg.setContent(html);
  await pg.screenshot({ path: out });
  if (errs.length) console.log('PAGE ERRORS:\n' + errs.join('\n'));
  console.log('sheet → ' + out);
  await b.close();
})();
