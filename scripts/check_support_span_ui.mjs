import { createRequire } from "node:module";
import { writeFile } from "node:fs/promises";
import assert from "node:assert/strict";
const { chromium } = createRequire(import.meta.url)(
  process.env.CODEX_BROWSER_MODULE ||
    "C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright",
);
const browser = await chromium.launch({
  executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe",
  headless: true,
});
const page = await browser.newPage({
  viewport: { width: 1512, height: 1080 },
  baseURL: "http://127.0.0.1:8765",
});
const report = { checks: [], errors: [] };
page.on("pageerror", (e) => report.errors.push(String(e)));
try {
  await page.goto("/");
  await page.getByRole("dialog").waitFor();
  await page.keyboard.press("Escape");
  await page
    .getByRole("textbox", { name: "筛选文献" })
    .fill("2106.09685v2.pdf");
  await page.locator(".document-item").first().click();
  await page
    .getByRole("textbox", { name: "研究问题" })
    .fill(
      "LoRA 中低秩矩阵 A、B 分别如何初始化？为什么刚开始训练时权重更新 ΔW 为零？不要把 A、B 互换。",
    );
  const pending = page.waitForResponse(
    (r) => r.url().endsWith("/api/ask") && r.request().method() === "POST",
    { timeout: 180000 },
  );
  await page.getByRole("textbox", { name: "研究问题" }).press("Enter");
  const response = await pending;
  assert(response.ok());
  report.answer = await response.json();
  assert(report.answer.model_answer?.length);
  const card = page.locator(".claim-card").first();
  await card
    .locator("summary", { hasText: "查看支持片段（模型初判）" })
    .click();
  assert.equal(
    (await card.locator("details blockquote").textContent()).trim(),
    report.answer.model_answer[0].support_span,
  );
  await card.getByRole("button", { name: "核对原文" }).click();
  await page.waitForFunction(
    () => document.querySelector('input[aria-label="当前页码"]')?.value === "4",
  );
  await page.locator('[data-testid="source-highlight"]').waitFor();
  await card.screenshot({
    path: "artifacts/quality-round5/support-span-desktop.png",
  });
  report.checks.push(
    "Enter submits a real local-model question; displayed support span matches response exactly; citation navigates to page 4",
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await card.screenshot({
    path: "artifacts/quality-round5/support-span-mobile.png",
  });
  assert(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  );
  report.checks.push(
    "Support passage expands without page-wide mobile overflow",
  );
  assert.deepEqual(report.errors, []);
} catch (e) {
  report.failure = String(e);
  await page.screenshot({
    path: `artifacts/quality-round5/support-ui-failure-${Date.now()}.png`,
  });
  throw e;
} finally {
  await writeFile(
    `artifacts/quality-round5/support-browser-${Date.now()}.json`,
    JSON.stringify(report, null, 2),
  );
  await browser.close();
  console.log(
    JSON.stringify(
      { checks: report.checks, errors: report.errors, failure: report.failure },
      null,
      2,
    ),
  );
}
