// Record one scripted run: node scripts/drive.mjs <mode> <seed> <course> <stopSeconds> [videoDir] -> prints the per-driver summary JSON.
import { chromium } from '/home/seb/jevlab/demos/jev-autopilot/node_modules/playwright-core/index.mjs';
const [mode, seed, course, stop, videoDir] = process.argv.slice(2);
const browser = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--no-sandbox'] });
const size = { width: 1920, height: 1080 };
const ctx = await browser.newContext({ viewport: size, deviceScaleFactor: 1, ...(videoDir ? { recordVideo: { dir: videoDir, size } } : {}) });
const page = await ctx.newPage();
page.on('console', (m) => { if (m.type() === 'error') console.error('[console]', m.text()); });
await page.goto(`http://127.0.0.1:3001/?mode=${mode}&seed=${seed}&course=${course}&stop=${stop}`);
const t0 = Date.now();
let snap = null;
while (Date.now() - t0 < Number(process.env.MAX_MS ?? 600_000)) {
  await page.waitForTimeout(1000);
  const running = await page.evaluate(() => window.__running());
  snap = await page.evaluate(() => window.__snapshot());
  if (!running || snap.every((d) => d.crashed)) break;
}
await page.waitForTimeout(2500);
const video = page.video();
await ctx.close();
if (video) console.error('video:', await video.path());
await browser.close();
console.log(JSON.stringify({ mode, seed: Number(seed), course, stop: Number(stop), drivers: snap }));
