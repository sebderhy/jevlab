// Fly one mission headless: node runs/fly.mjs <pilot> <seed> [videoDir] -> prints the flight record JSON.
import { chromium } from 'playwright-core';
const [pilot, seed, videoDir] = process.argv.slice(2);
const browser = await chromium.launch({
  executablePath: '/usr/bin/google-chrome',
  args: ['--no-sandbox', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
});
const ctx = await browser.newContext({
  viewport: { width: 960, height: 1080 },
  deviceScaleFactor: 1,
  ...(videoDir ? { recordVideo: { dir: videoDir, size: { width: 960, height: 1080 } } } : {}),
});
const page = await ctx.newPage();
page.on('console', (m) => { if (m.type() === 'error') console.error('[console]', m.text()); });
await page.goto(`http://127.0.0.1:5173/?pilot=${pilot}&seed=${seed}&auto=1${process.env.RENDER ? `&render=${process.env.RENDER}` : ''}${process.env.TIMESCALE ? `&timescale=${process.env.TIMESCALE}` : ''}`);
const t0 = Date.now();
let flight = null;
while (!flight && Date.now() - t0 < Number(process.env.MAX_MS ?? 240_000)) {
  await page.waitForTimeout(1000);
  flight = await page.evaluate(() => window.__flight ?? null);
}
if (!flight) console.error('timeout, last status:', JSON.stringify(await page.evaluate(() => window.__status ?? null)));
await page.waitForTimeout(2500); // keep the landing banner on screen
const video = page.video();
await ctx.close();
if (video) console.error('video:', await video.path());
await browser.close();
console.log(JSON.stringify(flight));
