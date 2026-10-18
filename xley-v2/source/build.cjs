// Build output/XLEY_Brand_Strategy_V2.pdf from source/deck.html with Chromium (Playwright),
// then render every page of the finished PDF to PNG for visual QA.
//
// Usage:  node source/build.cjs            (from the repo root)
// Needs:  playwright (Node), pdftoppm (poppler-utils); network access to Google Fonts.

const path = require('path');
const fs = require('fs');
const { execFileSync } = require('child_process');
const { chromium } = require('playwright');

const ROOT = path.resolve(__dirname, '..');
const DECK = path.join(__dirname, 'deck.html');
const OUT_DIR = path.join(ROOT, 'output');
const PDF = path.join(OUT_DIR, 'XLEY_Brand_Strategy_V2.pdf');
const QA_DIR = path.join(OUT_DIR, 'qa');

(async () => {
  fs.mkdirSync(QA_DIR, { recursive: true });
  const launch = { executablePath: process.env.CHROMIUM_PATH || undefined };
  if (process.env.HTTPS_PROXY) launch.proxy = { server: process.env.HTTPS_PROXY };
  const browser = await chromium.launch(launch);
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
  await page.goto('file://' + DECK, { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForFunction(() => window.__artDone === true, null, { timeout: 30000 });

  // Report fonts and art status so a missing font or image never ships silently.
  const status = await page.evaluate(() => ({
    baloo: document.fonts.check('800 20px "Baloo 2"'),
    nunito: document.fonts.check('400 12px "Nunito Sans"'),
    art: Array.from(document.querySelectorAll('[data-src]')).map(el => ({
      src: el.getAttribute('data-src'), loaded: el.classList.contains('loaded'),
    })),
    overflow: Array.from(document.querySelectorAll('.page')).map((p, i) => {
      const body = p.querySelector('.body');
      return body && body.scrollHeight > body.clientHeight + 1 ? i + 1 : null;
    }).filter(Boolean),
  }));
  console.log('fonts:', { baloo: status.baloo, nunito: status.nunito });
  const missing = status.art.filter(a => !a.loaded).map(a => a.src);
  console.log(`art: ${status.art.length - missing.length}/${status.art.length} images loaded`);
  if (missing.length) console.log('placeholders used for:', [...new Set(missing)].join(', '));
  if (status.overflow.length) console.log('WARNING body overflow on pages:', status.overflow.join(', '));

  await page.pdf({ path: PDF, width: '1280px', height: '720px', printBackground: true, preferCSSPageSize: true, tagged: true });
  await browser.close();
  console.log('wrote', path.relative(ROOT, PDF), Math.round(fs.statSync(PDF).size / 1024) + ' KB');

  for (const f of fs.readdirSync(QA_DIR)) if (f.endsWith('.png')) fs.unlinkSync(path.join(QA_DIR, f));
  execFileSync('pdftoppm', ['-png', '-r', '96', PDF, path.join(QA_DIR, 'page')]);
  console.log('QA renders in', path.relative(ROOT, QA_DIR));
})().catch(err => { console.error(err); process.exit(1); });
