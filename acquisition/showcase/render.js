// node render.js [fps] [only-times...]  -> frames/0000.jpg ... ; then ffmpeg -> showcase.mp4
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
(async () => {
  const fps = +(process.argv[2] || 30), only = process.argv.slice(3).map(Number);
  const b = await chromium.launch();
  const pg = await b.newPage({ viewport: { width: 540, height: 960 }, deviceScaleFactor: 2 });
  await pg.goto('file://' + path.resolve(__dirname, 'showcase.html'), { waitUntil: 'networkidle' });
  await pg.evaluate(() => document.fonts.ready);
  const dir = path.join(__dirname, only.length ? 'stills' : 'frames');
  fs.rmSync(dir, { recursive: true, force: true }); fs.mkdirSync(dir);
  const dur = await pg.evaluate(() => window.DURATION);
  const times = only.length ? only : [...Array(Math.round(dur * fps)).keys()].map(i => i / fps);
  for (let i = 0; i < times.length; i++) {
    await pg.evaluate(t => render(t), times[i]);
    await pg.screenshot({ path: path.join(dir, (only.length ? `t${times[i]}` : String(i).padStart(4, '0')) + '.jpg'), type: 'jpeg', quality: 92 });
  }
  await b.close();
})();
