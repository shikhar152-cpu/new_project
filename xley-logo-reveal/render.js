// Renders xley-reveal.html frame by frame and encodes it to MP4 with ffmpeg.
// Usage: node render.js [fps]
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const path = require('path');

const FPS = Number(process.argv[2] || 24);
const dir = __dirname;
const out = path.join(dir, 'xley_logo_reveal.mp4');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  await page.addInitScript(() => { window.__RENDERING__ = true; });
  // served over http so the logo image can be read back from the canvas
  const server = require('http').createServer((q, r) => require('fs').createReadStream(path.join(dir, decodeURIComponent(q.url.split('?')[0]))).on('error', () => { r.statusCode = 404; r.end(); }).pipe(r)).listen(0);
  await page.goto('http://127.0.0.1:' + server.address().port + '/xley-reveal.html');
  await page.evaluate(() => window.ready);
  const duration = await page.evaluate(() => window.DURATION);
  const total = Math.round(duration * FPS);

  const ff = spawn('ffmpeg', ['-y', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'png', '-i', '-',
    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '14', '-preset', 'slow', '-movflags', '+faststart', out],
    { stdio: ['pipe', 'ignore', 'inherit'] });

  for (let i = 0; i < total; i++) {
    const data = await page.evaluate(([t, i]) => { renderFrame(t, i); return document.getElementById('c').toDataURL('image/png'); }, [i / FPS, i]);
    ff.stdin.write(Buffer.from(data.split(',')[1], 'base64'));
    if (i % 30 === 0) process.stderr.write(`frame ${i}/${total}\n`);
  }
  ff.stdin.end();
  await new Promise(r => ff.on('close', r));
  await browser.close(); server.close();
  console.log('wrote', out);
})();
