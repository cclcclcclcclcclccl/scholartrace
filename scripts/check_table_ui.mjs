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
  await page.goto("http://127.0.0.1:8765");
  await page.getByRole("dialog").waitFor();
  await page.keyboard.press("Escape");
  await page
    .getByRole("textbox", { name: "筛选文献" })
    .fill("1706.03762v1_img.pdf");
  await page.locator(".document-item").first().click();
  await page.getByRole("button", { name: "文献管理", exact: true }).click();
  const panel = page.locator(".table-panel");
  await panel.locator(":scope > summary").click();
  const jump = panel.getByRole("spinbutton", { name: "当前页码" });
  await jump.fill("");
  assert.equal(await jump.inputValue(), "");
  await jump.fill("9");
  await jump.press("Enter");
  await panel.getByRole("button", { name: "表格候选 2", exact: true }).click();
  const pending = page.waitForResponse(
    (r) => r.url().endsWith("/api/jobs") && r.request().method() === "POST",
  );
  await panel
    .getByRole("button", { name: "提取所选表格", exact: true })
    .click();
  const job = await (await pending).json();
  report.job_id = job.id;
  await panel.locator(".table-result").waitFor({ timeout: 120000 });
  assert.equal(
    await panel.getByLabel("第 6 行第 3 列", { exact: true }).inputValue(),
    "91.3",
  );
  assert.equal(
    await panel.getByLabel("第 11 行第 3 列", { exact: true }).inputValue(),
    "92.7",
  );
  await panel.getByLabel("第 6 行第 3 列", { exact: true }).focus();
  await panel.locator(".table-cell-highlight").waitFor();
  report.checks.push(
    "Real scanned 12x3 table, both Transformer metrics, blank-editable page number and cell source highlight",
  );
  const original = await panel
    .getByLabel("第 2 行第 1 列", { exact: true })
    .inputValue();
  await panel
    .getByLabel("第 2 行第 1 列", { exact: true })
    .fill("Vinyals & Kaiser el al. (2014) [33]");
  await panel
    .getByRole("button", { name: "保存表格修改", exact: true })
    .click();
  await panel.getByText("表格修改已保存，初次提取与修改历史仍保留。").waitFor();
  const completed = await (
    await page.request.get("/api/jobs/" + job.id)
  ).json();
  report.artifact_id = completed.result.id;
  const saved = await (
    await page.request.get("/api/artifacts/" + report.artifact_id)
  ).json();
  assert.equal(saved.content.original_rows[1][0], original);
  assert.equal(saved.content.rows[1][0], "Vinyals & Kaiser el al. (2014) [33]");
  assert.equal(saved.content.edits.length, 1);
  assert.ok(
    saved.content.cells.length > 0,
    "Text-only corrections must keep source cell geometry",
  );
  await panel.getByLabel("第 6 行第 3 列", { exact: true }).focus();
  await panel.locator(".table-cell-highlight").waitFor();
  const csv = await (
    await page.request.get("/api/tables/" + report.artifact_id + "/export")
  ).text();
  assert.match(csv, /Transformer \(4 layers\),semi-supervised,92\.7/);
  const exported = await (
    await page.request.get(
      "/api/artifacts/" + report.artifact_id + "/export?format=json",
    )
  ).json();
  assert.equal(exported.content.original_rows[1][0], original);
  report.checks.push(
    "Correction persists with immutable initial OCR, revision history, real CSV and JSON downloads",
  );
  await panel
    .locator(".table-result")
    .screenshot({ path: "artifacts/quality-round2/table-desktop.png" });
  await page.getByRole("button", { name: "任务与成果", exact: true }).click();
  await page
    .locator(".artifact-list button")
    .filter({ hasText: "第 9 页表格" })
    .first()
    .click();
  const result = page.locator(".table-result");
  await result.waitFor();
  assert.equal(
    await result.getByLabel("第 2 行第 1 列", { exact: true }).inputValue(),
    "Vinyals & Kaiser el al. (2014) [33]",
  );
  await result.getByText("调整分列与查看初次提取", { exact: true }).click();
  await result
    .getByRole("button", { name: "按分列线重新排列", exact: true })
    .click();
  await result
    .getByText("已按新分列线重新排列，之前的单元格保留在历史中。")
    .waitFor();
  assert.equal(
    await result.getByLabel("第 11 行第 3 列", { exact: true }).inputValue(),
    "92.7",
  );
  const regenerated = await (
    await page.request.get("/api/artifacts/" + report.artifact_id)
  ).json();
  assert.equal(regenerated.content.revision, 2);
  assert.equal(
    regenerated.content.edits[1].rows[1][0],
    "Vinyals & Kaiser el al. (2014) [33]",
  );
  // Restore the verified correction after testing regrid history.
  await result
    .getByLabel("第 2 行第 1 列", { exact: true })
    .fill("Vinyals & Kaiser el al. (2014) [33]");
  await result
    .getByRole("button", { name: "保存表格修改", exact: true })
    .click();
  await result
    .getByText("表格修改已保存，初次提取与修改历史仍保留。")
    .waitFor();
  report.checks.push(
    "Task artifact reopens; regrid preserves earlier manual edits in history",
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await result.scrollIntoViewIfNeeded();
  assert.ok(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 2,
    ),
    "Mobile document overflows viewport",
  );
  await result.screenshot({
    path: "artifacts/quality-round2/table-mobile.png",
  });
  report.checks.push(
    "390px mobile layout has no page-level horizontal overflow",
  );
  assert.deepEqual(report.errors, []);
} catch (e) {
  report.failure = String(e);
  process.exitCode = 1;
  await page.screenshot({
    path: "artifacts/quality-round2/table-ui-failure.png",
    fullPage: true,
  });
} finally {
  await writeFile(
    "artifacts/quality-round2/table-ui-report.json",
    JSON.stringify(report, null, 2),
  );
  console.log(JSON.stringify(report));
  await browser.close();
}
