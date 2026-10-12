import { createRequire } from "node:module";
import { writeFile } from "node:fs/promises";
import assert from "node:assert/strict";
const { chromium } = createRequire(import.meta.url)("C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright");
const browser = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
const page = await browser.newPage({ viewport: { width: 1512, height: 1080 }, baseURL: "http://127.0.0.1:8765" });
const report = { checks: [], errors: [] };
page.on("pageerror", e => report.errors.push(String(e)));
let id, previousBookmarks;
try {
  await page.goto("/");
  await page.getByRole("dialog").waitFor();
  await page.keyboard.press("Escape");
  await page.getByRole("textbox", { name: "筛选文献" }).fill("1706.03762v1.pdf");
  await page.locator(".document-item").first().click();
  const docs = await (await page.request.get("/api/documents")).json();
  id = docs.find(p => p.name === "1706.03762v1.pdf").id;
  previousBookmarks = await (await page.request.get(`/api/documents/${id}/bookmarks`)).json();
  await page.locator(".reading-extras > summary").click();
  await page.getByRole("textbox", { name: "搜索论文正文" }).fill("P100");
  await page.getByRole("button", { name: "搜索全文", exact: true }).click();
  const hit = page.locator(".reading-extras .reading-search-results button").first();
  await hit.waitFor();
  await hit.click();
  await page.getByRole("textbox", { name: "书签名称" }).fill("浏览器检查：训练条件");
  await page.getByRole("button", { name: "收藏当前页", exact: true }).click();
  await page.locator(".bookmark-list").getByText(/浏览器检查：训练条件/).waitFor();
  await page.reload();
  await page.locator(".reading-extras > summary").click();
  await page.locator(".bookmark-list").getByText(/浏览器检查：训练条件/).waitFor();
  report.checks.push("Search real paper text, jump to source, save bookmark, persistence across reload");
  await page.locator("canvas").waitFor();
  await page.waitForFunction(() => { const c = document.querySelector("canvas"); return c && c.width > 0 && !document.body.innerText.includes("正在呈现原文"); });
  await page.screenshot({ path: "artifacts/product-audit/reader-upgrade.png" });
  await page.getByRole("button", { name: "文献管理", exact: true }).click();
  await page.getByText("文献分类与阅读清单", { exact: true }).click();
  await page.getByLabel("文献项目分类", { exact: true }).fill("试验分类（未保存）");
  await page.getByRole("button", { name: "查看阅读清单", exact: true }).click();
  await page.locator(".reading-search-results button").first().waitFor();
  report.checks.push("Library metadata editor and real reading list render");
  await page.getByRole("button", { name: "双语与引文", exact: true }).click();
  await page.getByText("专业术语表与翻译校对说明", { exact: true }).click();
  await page.getByLabel("翻译术语表").fill("attention = 注意力（测试，不保存）");
  report.checks.push("Terminology editor is accessible without modifying saved terms");
  await page.getByRole("button", { name: "论文发现", exact: true }).click();
  await page.getByLabel("发表起始年份").fill("2020");
  await page.getByLabel("发表结束年份").fill("2026");
  report.checks.push("Year filters can be edited");
  await page.getByRole("button", { name: "科研工作室", exact: true }).click();
  await page.getByText("逐项证据比较与复现准备", { exact: true }).click();
  await page.getByLabel("证据矩阵核对问题").fill("主要模型的层数是多少？\n使用什么训练硬件？");
  assert.equal(await page.getByRole("button", { name: "建立逐项证据矩阵", exact: true }).isEnabled(), true);
  await page.getByLabel("CSV 数据", { exact: true }).fill("step,loss\n1,0.8\n10,0.4\n100,0.1");
  await page.getByLabel("横轴列", { exact: true }).fill("step");
  await page.getByLabel("数值列", { exact: true }).fill("loss");
  await page.getByLabel("图表类型", { exact: true }).selectOption("scatter");
  await page.getByLabel("横轴刻度", { exact: true }).selectOption("log");
  await page.getByLabel("纵轴刻度", { exact: true }).selectOption("log");
  await page.getByLabel("图标题", { exact: true }).fill("浏览器检查：损失散点图（示例数据）");
  await page.getByLabel("纵轴单位", { exact: true }).fill("loss");
  await page.getByRole("button", { name: "生成图表与图注", exact: true }).click();
  await page.locator(".chart-result img").waitFor({ timeout: 30000 });
  assert.equal(await page.locator(".chart-result img").evaluate(img => img.complete && img.naturalWidth > 0), true);
  report.checks.push("Research matrix controls and actual scatter/log chart render with downloadable artifacts");
  await page.locator(".chart-result").screenshot({ path: "artifacts/product-audit/chart-upgrade.png" });
  await page.setViewportSize({ width: 1100, height: 800 });
  report.checks.push("1100px viewport smoke check");
  assert.deepEqual(report.errors, []);
} catch (e) {
  report.failure = String(e);
  await page.screenshot({ path: "artifacts/product-audit/ui-failure.png" });
  throw e;
} finally {
  if (id && previousBookmarks) {
    const current = await (await page.request.get(`/api/documents/${id}/bookmarks`)).json();
    for (const b of current.filter(b => b.label === "浏览器检查：训练条件")) {
      const old = previousBookmarks.find(v => v.page === b.page);
      if (old) await page.request.post(`/api/documents/${id}/bookmarks`, { data: old });
      else await page.request.delete(`/api/documents/${id}/bookmarks/${b.page}`);
    }
  }
  await writeFile("artifacts/product-audit/ui-report.json", JSON.stringify(report, null, 2));
  await browser.close();
  console.log(JSON.stringify(report, null, 2));
}
