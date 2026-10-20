// Renders index.html frame-by-frame with headless Chromium and pipes JPEG frames into ffmpeg.
// usage: node render.js frames 0.5,1.2,3.0     -> build/f_<t>.jpg previews
//        node render.js video [seconds]         -> build/out.mp4 (30 fps)
const {chromium} = require('playwright');
const {spawn} = require('child_process');
const path = require('path');

const DIR = __dirname, FPS = 30;
const [mode, arg] = process.argv.slice(2);

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({viewport: {width: 1920, height: 1080}, deviceScaleFactor: 1});
  page.on('console', m => console.log('page:', m.text()));
  await page.goto(`http://127.0.0.1:${process.env.PORT || 8123}/index.html`);
  await page.waitForFunction('window.READY === true', null, {timeout: 120000});
  const size = await page.evaluate(() => ({width: W, height: H}));
  await page.setViewportSize(size);

  if (mode === 'frames') {
    for (const t of arg.split(',').map(Number)) {
      await page.evaluate(t => window.draw(t), t);
      await page.screenshot({path: path.join(DIR, `f_${t.toFixed(2)}.jpg`), type: 'jpeg', quality: 82});
    }
  } else {
    const n = Math.round((Number(arg) || 10) * FPS);
    const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-c:v', 'mjpeg', '-framerate', String(FPS), '-i', '-',
      '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', path.join(DIR, 'out.mp4')],
      {stdio: ['pipe', 'inherit', 'inherit']});
    for (let f = 0; f < n; f++) {
      await page.evaluate(t => window.draw(t), f / FPS);
      const buf = await page.screenshot({type: 'jpeg', quality: 95});
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
      if (f % 30 === 0) console.log('frame', f, '/', n);
    }
    ff.stdin.end();
    await new Promise(r => ff.on('close', r));
    console.log('done');
  }
  await browser.close();
})();
