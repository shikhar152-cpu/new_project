// Build output/XLEY_Brand_Strategy_V2.pptx, an editable PowerPoint version of source/deck.html.
// Each page is rendered in Chromium and rebuilt slide by slide: boxes and rules become PowerPoint
// shapes, every block of text an editable text box, and photos, icons and diagrams are placed as
// images captured from the page.
//
// Usage:  node source/build_pptx.cjs       (from the repo root; run fetch_images.py first)
// Needs:  playwright and pptxgenjs (Node); network access to Google Fonts.
// The slides use the deck's fonts, Baloo 2 and Nunito Sans (free on Google Fonts). Install them,
// or open the file in Google Slides, for the slides to match the PDF.

const path = require('path');
const fs = require('fs');
const { chromium } = require('playwright');
const PptxGenJS = require('pptxgenjs');

const ROOT = path.resolve(__dirname, '..');
const DECK = path.join(__dirname, 'deck.html');
const OUT = path.join(ROOT, 'output', 'XLEY_Brand_Strategy_V2.pptx');
const IN = 1 / 96;   // CSS px -> inches: a 1280 x 720 page becomes a 13.33 x 7.5 in slide
const PT = 0.75;     // CSS px -> points
const SCALE = 2;     // capture images at 2x so they stay sharp

// Runs in the page. Returns, per .page, its background and an ordered list of items:
// box (rectangle), line (single border side), text (runs of styled text), img (capture id).
function extract() {
  const rgba = s => {
    const m = s && s.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const [r, g, b, a = 1] = m[1].split(/[ ,/]+/).filter(Boolean).map(Number);
    return { r, g, b, a };
  };
  const hex = c => [c.r, c.g, c.b].map(v => Math.round(v).toString(16).padStart(2, '0')).join('').toUpperCase();
  const shown = c => c && c.a > 0.01;
  const over = (c, base) => ({ r: c.r * c.a + base.r * (1 - c.a), g: c.g * c.a + base.g * (1 - c.a), b: c.b * c.a + base.b * (1 - c.a), a: 1 });

  // List dots are ::before pseudo-elements, which are not in the DOM: make them real spans.
  const PROPS = ['display', 'position', 'top', 'left', 'right', 'bottom', 'width', 'height', 'margin-top', 'margin-right',
    'margin-bottom', 'margin-left', 'background-color', 'border-radius', 'color', 'font-size', 'font-weight', 'vertical-align'];
  const pseudo = [];
  for (const el of document.querySelectorAll('.page *')) {
    for (const which of ['::before', '::after']) {
      const cs = getComputedStyle(el, which);
      if (cs.content && cs.content !== 'none' && cs.content !== 'normal') {
        const span = document.createElement('span');
        for (const p of PROPS) span.style.setProperty(p, cs.getPropertyValue(p));
        span.textContent = cs.content.replace(/^["']|["']$/g, '');
        pseudo.push([el, which, span]);
      }
    }
  }
  const off = document.createElement('style');
  off.textContent = '.pz-off::before, .pz-off::after { content: none !important; }';
  document.head.appendChild(off);
  for (const [el, which, span] of pseudo) {
    el.classList.add('pz-off');
    if (which === '::before') el.prepend(span); else el.append(span);
  }

  let caps = 0;
  const capture = el => (el.dataset.cap = String(++caps));
  const hasBox = cs => shown(rgba(cs.backgroundColor)) ||
    ['Top', 'Right', 'Bottom', 'Left'].some(s => parseFloat(cs[`border${s}Width`]) > 0 && cs[`border${s}Style`] !== 'none');
  const inline = (el, cs) => cs.display === 'inline' && !hasBox(cs) && !['IMG', 'svg', 'BR'].includes(el.tagName);
  const font = cs => cs.fontFamily.split(',')[0].replace(/["']/g, '').trim();
  const align = cs => (cs.textAlign === 'center' ? 'center' : cs.textAlign === 'right' || cs.textAlign === 'end' ? 'right' : 'left');

  return [...document.querySelectorAll('.page')].map(pg => {
    const P = pg.getBoundingClientRect();
    const base = rgba(getComputedStyle(pg).backgroundColor);
    const items = [];
    const rel = r => ({ x: r.left - P.left, y: r.top - P.top, w: r.width, h: r.height });
    const color = c => (c.a < 1 ? hex(over(c, base)) : hex(c));

    const runStyle = cs => ({
      font: font(cs), size: parseFloat(cs.fontSize), bold: parseInt(cs.fontWeight, 10) >= 600,
      italic: cs.fontStyle === 'italic', color: color(rgba(cs.color)), ls: parseFloat(cs.letterSpacing) || 0,
      upper: cs.textTransform === 'uppercase',
    });

    // Gather the text of el and its inline descendants as styled runs; block-level children are
    // returned in `blocks` to become their own items.
    const collect = (el, runs, nodes, blocks) => {
      for (const n of el.childNodes) {
        if (n.nodeType === 3) {
          const text = n.textContent.replace(/\s+/g, ' ');
          if (!text) continue;
          const st = runStyle(getComputedStyle(n.parentElement));
          runs.push({ text: st.upper ? text.toUpperCase() : text, ...st });
          nodes.push(n);
        } else if (n.nodeType === 1) {
          const cs = getComputedStyle(n);
          if (cs.display === 'none') continue;
          if (n.tagName === 'BR') runs.push({ br: true });
          else if (inline(n, cs)) collect(n, runs, nodes, blocks);
          else blocks.push(n);
        }
      }
    };

    const textItem = (cs, runs, nodes) => {
      const rects = [];
      for (const n of nodes) {
        const rg = document.createRange();
        rg.selectNodeContents(n);
        for (const b of rg.getClientRects()) if (b.width > 0.5 && b.height > 0.5) rects.push(b);
      }
      if (!rects.length) return;
      // Trim spaces at the start and end of each line.
      const lines = [[]];
      for (const r of runs) { if (r.br) lines.push([]); else lines[lines.length - 1].push(r); }
      for (const ln of lines) {
        if (ln.length) { ln[0].text = ln[0].text.replace(/^ +/, ''); ln[ln.length - 1].text = ln[ln.length - 1].text.replace(/ +$/, ''); }
      }
      const L = Math.min(...rects.map(b => b.left)), T = Math.min(...rects.map(b => b.top));
      const R = Math.max(...rects.map(b => b.right)), B = Math.max(...rects.map(b => b.bottom));
      const lh = cs.lineHeight === 'normal' ? parseFloat(cs.fontSize) * 1.3 : parseFloat(cs.lineHeight);
      const tops = rects.map(b => b.top).sort((a, b) => a - b);
      let rows = 1;
      for (let i = 1; i < tops.length; i++) if (tops[i] - tops[i - 1] > lh * 0.6) rows++;
      items.push({
        kind: 'text', ...rel({ left: L, top: T, width: R - L, height: B - T }), align: align(cs),
        rows, lineHeight: lh, runs: lines.map(ln => ln.filter(r => r.text)),
      });
    };

    const boxItems = (cs, r) => {
      const fill = rgba(cs.backgroundColor);
      const sides = ['Top', 'Right', 'Bottom', 'Left'].map(s => ({
        w: parseFloat(cs[`border${s}Width`]) || 0, style: cs[`border${s}Style`], c: rgba(cs[`border${s}Color`]),
      })).map(s => ({ ...s, on: s.w > 0 && s.style !== 'none' && shown(s.c) }));
      const same = sides.every(s => s.on && s.w === sides[0].w && s.style === sides[0].style && hex(s.c) === hex(sides[0].c));
      const rad = cs.borderTopLeftRadius.endsWith('%')
        ? parseFloat(cs.borderTopLeftRadius) / 100 * Math.min(r.width, r.height)
        : parseFloat(cs.borderTopLeftRadius) || 0;
      const line = s => ({ color: hex(s.c), alpha: s.c.a, w: s.w, dash: s.style === 'dashed' ? 'dash' : s.style === 'dotted' ? 'sysDot' : 'solid' });
      if (shown(fill) || same) {
        items.push({
          kind: 'box', ...rel(r), radius: Math.min(rad, r.width / 2, r.height / 2),
          fill: shown(fill) ? { color: hex(fill), alpha: fill.a } : null, line: same ? line(sides[0]) : null,
        });
      }
      if (!same) {
        const [t, rt, b, l] = sides, R = rel(r);
        const side = (s, x, y, w, h, horizontal) => {
          if (!s.on) return;
          if (s.style === 'solid' || !horizontal) items.push({ kind: 'box', x, y, w, h, radius: 0, fill: { color: hex(s.c), alpha: s.c.a }, line: null });
          else items.push({ kind: 'line', x, y: y + h / 2, w, h: 0, ...line(s) });
        };
        side(t, R.x, R.y, R.w, t.w, true);
        side(b, R.x, R.y + R.h - b.w, R.w, b.w, true);
        side(l, R.x, R.y, l.w, R.h, false);
        side(rt, R.x + R.w - rt.w, R.y, rt.w, R.h, false);
      }
    };

    const svgItem = (svg, r) => {
      items.push({ kind: 'img', cap: capture(svg), ...rel(r), alt: svg.getAttribute('aria-label') || '' });
      // SVG labels stay editable: each <text> becomes a text box and is left out of the image.
      for (const t of svg.querySelectorAll('text')) {
        const cs = getComputedStyle(t), tr = t.getBoundingClientRect();
        const fill = rgba(cs.fill) || rgba(cs.color);
        const anchor = t.getAttribute('text-anchor') || cs.textAnchor;
        items.push({
          kind: 'text', ...rel(tr), rows: 1, lineHeight: tr.height, align: anchor === 'middle' ? 'center' : anchor === 'end' ? 'right' : 'left',
          runs: [[{ text: t.textContent.trim(), font: font(cs), size: parseFloat(cs.fontSize), bold: parseInt(cs.fontWeight, 10) >= 600,
            italic: false, color: color(fill), ls: 0, upper: false }]],
        });
      }
    };

    const walk = el => {
      const cs = getComputedStyle(el);
      if (cs.display === 'none' || cs.visibility === 'hidden') return;
      const r = el.getBoundingClientRect();
      if (el.tagName === 'svg') { if (r.width > 1 && r.height > 1) svgItem(el, r); return; }
      if (el.tagName === 'IMG') {
        items.push({ kind: 'img', cap: capture(el), photo: true, ...rel(r), alt: el.alt || el.closest('[data-alt]')?.dataset.alt || '' });
        return;
      }
      if (cs.backgroundImage !== 'none') { items.push({ kind: 'img', cap: capture(el), ...rel(r), alt: '' }); return; }
      if (el !== pg && r.width >= 1 && r.height >= 1) boxItems(cs, r);
      const runs = [], nodes = [], blocks = [];
      collect(el, runs, nodes, blocks);
      if (runs.some(x => x.text && x.text.trim())) textItem(cs, runs, nodes);
      blocks.forEach(walk);
    };
    walk(pg);
    return { bg: hex(base), items };
  });
}

(async () => {
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  const launch = { executablePath: process.env.CHROMIUM_PATH || undefined };
  if (process.env.HTTPS_PROXY) launch.proxy = { server: process.env.HTTPS_PROXY };
  const browser = await chromium.launch(launch);
  const page = await browser.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: SCALE });
  await page.goto('file://' + DECK, { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForFunction(() => window.__artDone === true, null, { timeout: 30000 });
  const slides = await page.evaluate(extract);

  // Photos keep what is behind their rounded corners (JPEG); icons and diagrams are captured
  // alone on a transparent background (PNG), without their SVG text.
  const grab = async it => {
    const sel = `[data-cap="${it.cap}"]`;
    const css = it.photo
      ? `${sel} ~ * { visibility: hidden !important; }`
      : `html, body { background: transparent !important; } body * { visibility: hidden !important; }
         ${sel}, ${sel} *, svg defs, svg defs * { visibility: visible !important; } ${sel} text { visibility: hidden !important; }`;
    const style = await page.addStyleTag({ content: css });
    const buf = await page.locator(sel).screenshot(it.photo ? { type: 'jpeg', quality: 88 } : { omitBackground: true });
    await style.evaluate(n => n.remove());
    return (it.photo ? 'image/jpeg' : 'image/png') + ';base64,' + buf.toString('base64');
  };

  const pres = new PptxGenJS();
  pres.layout = 'LAYOUT_WIDE';
  pres.title = 'XLEY Brand Strategy V2';
  pres.theme = { headFontFace: 'Baloo 2', bodyFontFace: 'Nunito Sans' };
  const tr = a => Math.round((1 - a) * 100);

  let n = 0;
  for (const s of slides) {
    const slide = pres.addSlide();
    slide.background = { color: s.bg };
    for (const it of s.items) {
      const pos = { x: it.x * IN, y: it.y * IN, w: Math.max(it.w, 0) * IN, h: Math.max(it.h, 0) * IN };
      if (it.kind === 'box') {
        const rounded = it.radius > 0.5;
        slide.addShape(rounded ? pres.ShapeType.roundRect : pres.ShapeType.rect, {
          ...pos, objectName: `Shape ${++n}`, rectRadius: rounded ? it.radius * IN : undefined,
          fill: it.fill ? { color: it.fill.color, transparency: tr(it.fill.alpha) } : { type: 'none' },
          line: it.line ? { color: it.line.color, transparency: tr(it.line.alpha), width: it.line.w * PT, dashType: it.line.dash } : { type: 'none' },
        });
      } else if (it.kind === 'line') {
        slide.addShape(pres.ShapeType.line, {
          ...pos, objectName: `Rule ${++n}`, line: { color: it.color, transparency: tr(it.alpha), width: it.w ? it.w * PT : 0.75, dashType: it.dash },
        });
      } else if (it.kind === 'img') {
        slide.addImage({ ...pos, data: await grab(it), altText: it.alt || undefined, objectName: `Image ${++n}` });
      } else if (it.kind === 'text') {
        // PowerPoint's fonts measure a little differently from Chromium's: give each box slack so
        // lines do not re-wrap, and keep one-line labels on one line.
        const slack = Math.max(6, it.w * 0.06);
        const x = it.align === 'center' ? it.x - slack / 2 : it.align === 'right' ? it.x - slack : it.x;
        const runs = [];
        it.runs.forEach((line, li) => line.forEach((r, ri) => runs.push({
          text: r.text,
          options: {
            fontFace: r.font, fontSize: +(r.size * PT).toFixed(1), bold: r.bold, italic: r.italic, color: r.color,
            charSpacing: r.ls ? +(r.ls * PT).toFixed(2) : undefined,
            breakLine: ri === line.length - 1 && li < it.runs.length - 1,
          },
        })));
        if (!runs.length) continue;
        slide.addText(runs, {
          x: x * IN, y: it.y * IN, w: (it.w + slack) * IN, h: Math.max(it.h, it.lineHeight) * IN,
          margin: 0, valign: 'top', align: it.align, wrap: it.rows > 1, fit: 'none', isTextBox: true,
          lineSpacing: it.rows > 1 ? +(it.lineHeight * PT).toFixed(1) : undefined,
          paraSpaceBefore: 0, paraSpaceAfter: 0, objectName: `Text ${++n}`,
        });
      }
    }
  }
  await browser.close();
  await pres.writeFile({ fileName: OUT });
  console.log('wrote', path.relative(ROOT, OUT), Math.round(fs.statSync(OUT).size / 1024) + ' KB,', slides.length, 'slides');
})().catch(err => { console.error(err); process.exit(1); });
