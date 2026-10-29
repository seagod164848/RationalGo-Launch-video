// Full-page phone-width screenshot of a generated site + the y-offset of every <section id>.
// The scroll animation is then cut from this one tall image by ffmpeg, which stays sharp
// and is deterministic (no flaky screen recording).
//   node capture_site.mjs out/sites/<slug>/index.html out/video/<slug>/site.png
import { createRequire } from 'node:module';
import { writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

// require() honours NODE_PATH / global installs, which ESM import does not.
const { chromium } = createRequire(import.meta.url)('playwright');

const [, , htmlPath, pngPath] = process.argv;
const DPR = 2.5; // 432 css px * 2.5 = 1080 px wide
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 432, height: 900 }, deviceScaleFactor: DPR });
await page.goto('file://' + resolve(htmlPath), { waitUntil: 'networkidle' }).catch(() => {});
await page.evaluate(() => document.fonts.ready);
// The sticky claim bar would be stamped across the whole scroll; it's shown on the page itself, not in the video.
await page.addStyleTag({ content: '.claim{display:none!important}' });
const sections = await page.evaluate(() => {
  const out = { top: 0 };
  for (const el of document.querySelectorAll('section[id], header.hero')) {
    out[el.id || 'hero'] = Math.round(el.getBoundingClientRect().top + window.scrollY);
  }
  out.__height = document.documentElement.scrollHeight;
  return out;
});
for (const k of Object.keys(sections)) sections[k] = Math.round(sections[k] * DPR);
await page.screenshot({ path: pngPath, fullPage: true });
writeFileSync(pngPath.replace(/\.png$/, '.sections.json'), JSON.stringify(sections, null, 1));
await browser.close();
