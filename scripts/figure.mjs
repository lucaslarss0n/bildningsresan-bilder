// Renders a figure drawn by Claude to two JPEGs, one for light and one for dark mode.
//
//   node scripts/figure.mjs path/to/figure.html out/name
//   -> out/name-light.jpg and out/name-dark.jpg (1500 px wide), sizes printed as JSON
//
// figure.html holds only the figure's own markup (and an optional <style>). It is placed in
// a 600 px wide frame that sets the font and these colour variables, so use them instead of
// fixed colours: --bg --fg --muted --line --box --strong --a1 --a2 --a3 --a4 (accents).
// Inline <svg> may use them too, e.g. stroke="var(--fg)".
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const [, , src, outBase] = process.argv;
if (!src || !outBase) { console.error("usage: node scripts/figure.mjs figure.html out/name"); process.exit(2); }
const require = createRequire(import.meta.url);
const fontDir = path.dirname(require.resolve("@fontsource/hanken-grotesk/package.json")) + "/files/";
const face = w => {
  const b64 = fs.readFileSync(`${fontDir}hanken-grotesk-latin-${w}-normal.woff2`).toString("base64");
  return `@font-face{font-family:H;src:url(data:font/woff2;base64,${b64}) format("woff2");font-weight:${w}}`;
};
const themes = {
  light: "--bg:#F4F3EF;--fg:#1B1B19;--muted:#6E6E68;--line:#D6D5CF;--box:#FFFFFF;--strong:#1B1B19;--a1:#2F6690;--a2:#B5533C;--a3:#3F6B57;--a4:#8A6D1F",
  dark: "--bg:#1F1F1D;--fg:#ECECE8;--muted:#9A9A93;--line:#3A3A37;--box:#2A2A28;--strong:#ECECE8;--a1:#7FB0D8;--a2:#E08A70;--a3:#8FBFA8;--a4:#D9B866",
};
const body = fs.readFileSync(src, "utf8");
const page = t => `<!doctype html><html><head><meta charset="utf-8"><style>${face(400)}${face(500)}${face(600)}
:root{${themes[t]}}*{box-sizing:border-box;margin:0}
body{font-family:H,sans-serif;color:var(--fg);background:var(--bg);width:600px;padding:22px 20px 18px;font-size:15px;line-height:1.35}
</style></head><body>${body}</body></html>`;

const exe = fs.existsSync("/opt/pw-browsers/chromium") ? "/opt/pw-browsers/chromium" : undefined;
const browser = await chromium.launch(exe ? { executablePath: exe } : {});
const out = {};
fs.mkdirSync(path.dirname(outBase), { recursive: true });
for (const t of Object.keys(themes)) {
  const p = await browser.newPage({ viewport: { width: 600, height: 400 }, deviceScaleFactor: 2.5 });
  await p.setContent(page(t), { waitUntil: "load" });
  await p.evaluate(() => document.fonts.ready);
  const file = `${outBase}-${t}.jpg`;
  await p.screenshot({ path: file, fullPage: true, type: "jpeg", quality: 86 });
  const size = await p.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.scrollHeight]);
  out[t] = { file, w: Math.round(size[0] * 2.5), h: Math.round(size[1] * 2.5), bytes: fs.statSync(file).size };
  await p.close();
}
await browser.close();
console.log(JSON.stringify(out));
