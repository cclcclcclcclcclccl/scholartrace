import { createRequire } from "node:module";
import { writeFile } from "node:fs/promises";
const { chromium } = createRequire(import.meta.url)("C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright");
const browser = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.goto("http://127.0.0.1:8765/");
  await page.getByRole("dialog").waitFor();
  await page.keyboard.press("Escape");
  await page.locator(".document-item small").first().waitFor();
  const result = await page.evaluate(() => {
    const list = document.querySelector(".document-list");
    const r = list.getBoundingClientRect();
    const rgb = text => (text.match(/[\d.]+/g) || []).map(Number);
    const luminance = values => values.slice(0, 3).reduce((total, value, index) => {
      const x = value / 255;
      return total + [0.2126, 0.7152, 0.0722][index] * (x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4);
    }, 0);
    const sample = document.querySelector(".document-item small");
    let ancestor = sample;
    let background;
    while (ancestor) {
      const value = getComputedStyle(ancestor).backgroundColor;
      const channels = rgb(value);
      if (channels.length === 3 || channels[3] === 1) { background = value; break; }
      ancestor = ancestor.parentElement;
    }
    const color = getComputedStyle(sample).color;
    const l1 = luminance(rgb(color)), l2 = luminance(rgb(background || "rgb(255,255,255)"));
    return {
      viewport: { width: innerWidth, height: innerHeight },
      topLevelNavigationCount: document.querySelectorAll(".nav-list button").length,
      navigationHeight: document.querySelector(".nav-list").getBoundingClientRect().height,
      documentListHeight: r.height,
      fullyVisibleDocumentRows: [...list.querySelectorAll(".document-item")].filter(e => { const a = e.getBoundingClientRect(); return a.top >= r.top && a.bottom <= r.bottom; }).length,
      metadataSample: { fontSize: getComputedStyle(sample).fontSize, color, background, contrastRatio: Math.round((Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05) * 100) / 100 },
      note: "One visible metadata text sample, not a full accessibility audit",
    };
  });
  await writeFile("artifacts/competitor-audit-2026-10-13/local-layout-metrics.json", JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
} finally { await browser.close(); }
