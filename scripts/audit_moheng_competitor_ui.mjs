import { createRequire } from "node:module";
import { mkdir, writeFile } from "node:fs/promises";
const { chromium } = createRequire(import.meta.url)(
  "C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright",
);
const root = "artifacts/moheng-final-20261021/competitors/screens";
await mkdir(root, { recursive: true });
const proxyUrl = process.env.HTTPS_PROXY || process.env.https_proxy;
const parsed = proxyUrl ? new URL(proxyUrl) : null;
const browser = await chromium.launch({
  executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe",
  headless: true,
  ...(parsed ? { proxy: { server: parsed.origin, bypass: "localhost,127.0.0.1", ...(parsed.username ? { username: decodeURIComponent(parsed.username), password: decodeURIComponent(parsed.password) } : {}) } } : {}),
});
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
const reports = [];
async function capture(id, url, scope) {
  const page = await context.newPage();
  const report = { id, requested_url: url, scope };
  try {
    const response = await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForTimeout(2000);
    report.status = response?.status();
    report.url = page.url();
    report.title = await page.title();
    report.text = (await page.locator("body").innerText()).slice(0, 30000);
    await page.screenshot({ path: `${root}/${id}.png` });
    console.log(id, report.status, report.title.slice(0, 100));
  } catch (e) {
    report.error = String(e);
    console.log(id, report.error.slice(0, 140));
  } finally { reports.push(report); await page.close(); }
}
try {
  const sites = [
    ["pubmed", "https://pubmed.ncbi.nlm.nih.gov/?term=attention+transformer", "public search results"],
    ["semantic-reader", "https://www.semanticscholar.org/product/semantic-reader", "public product demonstrations"],
    ["elicit", "https://elicit.com/", "public product page, not authenticated app"],
    ["consensus", "https://consensus.app/", "public search interface"],
    ["semantic-scholar", "https://www.semanticscholar.org/search?q=low%20rank%20adaptation&sort=relevance", "public search results"],
    ["scispace", "https://scispace.com/", "public interface"],
    ["notebooklm", "https://notebooklm.google/", "public product page"],
    ["researchrabbit", "https://www.researchrabbit.ai/", "public product page"],
    ["litmaps", "https://www.litmaps.com/", "public product page"],
    ["connectedpapers", "https://www.connectedpapers.com/", "public search interface"],
    ["zotero", "https://www.zotero.org/", "public product screenshot"],
    ["paperpile", "https://paperpile.com/", "public product screenshot"],
    ["jenni", "https://jenni.ai/", "public product page"],
    ["biorender", "https://www.biorender.com/", "public product page"],
    ["xiaolujing", "https://www.xljsci.com/", "public product page"],
    ["ima", "https://ima.qq.com/", "public product page"],
    ["metaso", "https://metaso.cn/", "public search interface"],
    ["aminer", "https://www.aminer.cn/", "public interface"],
  ];
  const selected = sites.filter(([id]) => ["semantic-reader","elicit","consensus","researchrabbit","connectedpapers","zotero","paperpile","biorender"].includes(id));
  for (let i = 0; i < selected.length; i += 3) await Promise.allSettled(selected.slice(i, i + 3).map(args => capture(...args)));
} finally {
  await writeFile(`${root}/observations.json`, JSON.stringify(reports, null, 2));
  await browser.close();
}
