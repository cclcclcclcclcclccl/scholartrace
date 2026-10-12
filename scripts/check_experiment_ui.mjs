import { createRequire } from "node:module";
import { writeFile } from "node:fs/promises";
import assert from "node:assert/strict";
const { chromium } = createRequire(import.meta.url)(
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
  await page.getByRole("button", { name: "科研工作室", exact: true }).click();
  const card = page.locator(".protocol-editor");
  await card.locator(":scope > summary").click();
  const fields = {
    实验名称: "浏览器验收：检索实验设计卡",
    待验证假设: "混合检索可能提高有出处的答案覆盖率。",
    数据与许可: "本地开发验证题集，非正式独立评测。",
    数据划分: "固定开发题集与测试题集分离；不得用测试答案调提示。",
    对照基线: "BM25 检索",
    实验变量与取值: "BM25 / 混合检索，保持相同 top-k",
    固定条件: "同一语料快照、同一模型、同一问题与上下文预算",
    主要指标: "score",
    判定标准: "分别报告证据覆盖、错误回答和漏答；不按单题宣布胜出。",
    资源与试跑: "本地 CPU，先做 3 个种子的流程检查。",
    失败与负结果: "索引失败单独记录；低分作为有效结果保留。",
  };
  for (const [name, value] of Object.entries(fields))
    await card.getByLabel(name, { exact: true }).fill(value);
  await card.getByLabel("实验任务类别").selectOption("retrieval");
  const created = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/experiments/protocols") &&
      r.request().method() === "POST",
  );
  await card
    .getByRole("button", { name: "保存实验设计卡", exact: true })
    .click();
  const protocol = await (await created).json();
  report.protocol_id = protocol.id;
  await card.getByText(/第 1 版已保存/).waitFor();
  report.checks.push("Fill and save structured protocol through actual UI");
  const lab = page.locator(".measurement-lab");
  await lab.locator(":scope > summary").click();
  await lab
    .getByRole("button", { name: "载入示例（非实验结果）", exact: true })
    .click();
  await lab
    .getByRole("button", { name: "刷新实验设计列表", exact: true })
    .click();
  await lab.getByLabel("关联实验设计").selectOption(protocol.id);
  await lab.getByLabel("误差棒含义").selectOption("ci95");
  await lab.getByLabel("统计标题").fill("浏览器验收：重复运行示例统计");
  const measured = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/experiments/analyze") &&
      r.request().method() === "POST",
  );
  await lab
    .getByRole("button", { name: "计算并保存重复实验统计", exact: true })
    .click();
  const response = await measured;
  assert(response.ok());
  const result = await response.json();
  report.measurement_id = result.id;
  await lab.locator(".measurement-result img").waitFor();
  await lab.locator(".measurement-result img").evaluate((img) => img.decode());
  assert.equal(result.summary[0].mean, 71);
  assert.equal(result.summary[0].sd, 1);
  assert.equal(result.protocol_snapshot.revision, 1);
  assert.equal(result.spec.data_label, "example");
  await lab
    .locator(".measurement-result")
    .screenshot({ path: "artifacts/research-round3/statistics-ui.png" });
  report.checks.push(
    "Compute real sample statistics, CI error bars, raw dots and immutable protocol revision from example CSV",
  );
  await card.getByLabel("对照基线", { exact: true }).fill("修改后的对照基线");
  await card
    .getByRole("button", { name: "保存实验设计卡", exact: true })
    .click();
  await card.getByText(/第 2 版已保存/).waitFor();
  const saved = await (
    await page.request.get(`/api/artifacts/${result.id}`)
  ).json();
  assert.equal(saved.content.protocol_snapshot.revision, 1);
  report.checks.push(
    "Editing protocol creates revision 2 while old measurements stay on revision 1",
  );
  const bundle = await page.request.get(
    `/api/experiments/${result.id}/files/bundle.zip`,
  );
  assert(bundle.ok());
  await writeFile(
    "artifacts/research-round3/reproduction.zip",
    await bundle.body(),
  );
  await page.getByRole("button", { name: "任务与成果", exact: true }).click();
  await page
    .getByRole("button")
    .filter({ hasText: "浏览器验收：重复运行示例统计" })
    .click();
  await page.locator(".measurement-result img").waitFor();
  report.checks.push(
    "Reopen persisted statistics and download reproducibility bundle",
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(200);
  assert(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  );
  await page.screenshot({
    path: "artifacts/research-round3/statistics-mobile.png",
  });
  report.checks.push(
    "390px mobile layout has no page-wide horizontal overflow",
  );
  assert.deepEqual(report.errors, []);
} catch (e) {
  report.failure = String(e);
  await page.screenshot({ path: "artifacts/research-round3/ui-failure.png" });
  throw e;
} finally {
  await writeFile(
    "artifacts/research-round3/browser-report.json",
    JSON.stringify(report, null, 2),
  );
  await browser.close();
  console.log(JSON.stringify(report, null, 2));
}
