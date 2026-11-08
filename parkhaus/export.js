// Ticket-SVG in PNG (zum Ansehen) und PDF (zum Drucken) umwandeln.
// Nutzt den vorinstallierten Chromium ueber Playwright.
//
// Aufruf:  node parkhaus/export.js  <ticket.svg>  <ziel-ohne-endung>
// Ergebnis: <ziel>.png und <ziel>.pdf  (iPhone-tauglich)

const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  const src = process.argv[2];
  const out = process.argv[3];
  if (!src || !out) {
    console.error('Aufruf: node parkhaus/export.js <ticket.svg> <ziel-ohne-endung>');
    process.exit(1);
  }
  const svg = fs.readFileSync(src, 'utf8');
  const browser = await chromium.launch();
  const page = await browser.newPage({ deviceScaleFactor: 3 });
  const html = `<!doctype html><html><head><meta charset="utf-8">
    <style>html,body{margin:0;padding:24px;background:#fff;display:inline-block}</style>
    </head><body>${svg}</body></html>`;
  await page.setContent(html, { waitUntil: 'networkidle' });
  const el = await page.$('svg');
  const box = await el.boundingBox();
  await page.screenshot({
    path: out + '.png',
    clip: { x: box.x - 24, y: box.y - 24, width: box.width + 48, height: box.height + 48 },
  });
  await page.pdf({
    path: out + '.pdf',
    width: (box.width + 96) + 'px',
    height: (box.height + 96) + 'px',
    printBackground: true,
  });
  await browser.close();
  console.log(`geschrieben: ${out}.png  +  ${out}.pdf`);
})();
