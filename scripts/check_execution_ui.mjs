import { createRequire } from "node:module";
import { readFile, writeFile } from "node:fs/promises";
import assert from "node:assert/strict";
const { chromium } = createRequire(import.meta.url)(
  process.env.CODEX_BROWSER_MODULE ||
    "C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright",
);
const folder = "artifacts/quality-round4";
const browser = await chromium.launch({
  executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe",
  headless: true,
});
const page = await browser.newPage({
  viewport: { width: 1440, height: 1000 },
  baseURL: "http://127.0.0.1:8765",
});
const report = { checks: [], errors: [] };
page.on("pageerror", (error) => report.errors.push(String(error)));
try {
  const live = JSON.parse(
    await readFile(`${folder}/structured-plan-first.json`, "utf8"),
  );
  assert.equal(live.state, "completed");
  const source = live.result;
  await page.goto("/");
  await page.getByRole("dialog").waitFor();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "任务与成果", exact: true }).click();
  const escaped = source.title.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  await page
    .locator(".artifact-list button")
    .filter({ hasText: new RegExp("^writing\\s*" + escaped + "$") })
    .click();
  await page
    .getByRole("heading", { name: source.title, exact: true })
    .waitFor();
  const card = page.locator(".artifact-result .protocol-editor");
  await card.locator(":scope > summary").click();
  await card.locator(".execution-parameters > summary").click();
  assert.equal(
    await card.getByLabel("总隐藏维度 d_model").inputValue(),
    String(source.execution_draft.execution.d_model),
  );
  assert.equal(
    await card.getByLabel("实验任务类别").inputValue(),
    "language_modeling",
  );
  report.checks.push(
    "Real model structured settings populate editable design, task, metric and seeds",
  );
  const fields = {
    实验名称: "浏览器验收：结构化注意力试跑设计",
    待验证假设: "头数可能影响语言建模效果，尚未训练。",
    数据与许可: "拟议 WikiText-2，版本和许可待核对",
    数据划分: "官方固定训练、验证、测试划分；不在测试集调参。",
    对照基线: "一个注意力头",
    实验变量与取值: "只改变头数，各组从零训练",
    固定条件: "同一数据、模型宽度、训练步数和优化器；计时使用相同条件。",
    判定标准: "保留全部运行，仅描述观察到的差异；实用阈值待确定。",
    资源与试跑: "本地 CPU，完整训练资源待测；本次只运行形状预检。",
    失败与负结果: "保留失败日志、重跑次数和有效负结果。",
  };
  for (const [label, value] of Object.entries(fields))
    await card.getByLabel(label, { exact: true }).fill(value);
  await card.getByLabel("注意力头数列表").fill("1, 3");
  const invalid = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/experiments/protocols") &&
      r.request().method() === "POST",
  );
  await card
    .getByRole("button", { name: "保存实验设计卡", exact: true })
    .click();
  assert.equal((await invalid).status(), 422);
  await card.getByRole("status").filter({ hasText: "整除" }).waitFor();
  report.checks.push(
    "Invalid head divisibility rejected with visible actionable message",
  );
  await card
    .getByLabel("注意力头数列表")
    .fill(source.execution_draft.execution.heads.join(", "));
  const created = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/experiments/protocols") &&
      r.request().method() === "POST",
  );
  await card
    .getByRole("button", { name: "保存实验设计卡", exact: true })
    .click();
  const response = await created;
  assert(response.ok());
  const protocol = await response.json();
  report.protocol_id = protocol.id;
  await card.getByText("当前保存版本：第 1 版", { exact: true }).waitFor();
  const checked = page.waitForResponse(
    (r) =>
      r.url().endsWith(`/protocols/${protocol.id}/preflight`) &&
      r.request().method() === "POST",
  );
  await card
    .getByRole("button", { name: "预检已保存的第 1 版", exact: true })
    .click();
  const cr = await checked;
  assert(cr.ok());
  const result = await cr.json();
  report.result_id = result.id;
  assert.equal(
    result.results.length,
    source.execution_draft.execution.heads.length,
  );
  assert(result.results.every((r) => r.finite && r.normalized_attention));
  assert.equal(result.actual_batch_size, 1);
  assert.equal(result.actual_sequence_length, 16);
  await card.locator(".execution-result").waitFor();
  await card
    .locator(".execution-result")
    .screenshot({ path: `${folder}/execution-ui.png` });
  const downloaded = await page.request.get(
    `/api/artifacts/${result.id}/export?format=json`,
  );
  assert(downloaded.ok());
  await writeFile(`${folder}/preflight-download.json`, await downloaded.body());
  report.checks.push(
    "Save protocol, run actual CPU attention shape check, and download immutable parameters/results",
  );
  await page
    .getByRole("button", { name: "刷新任务和文献库", exact: true })
    .click();
  const item = await (
    await page.request.get(`/api/artifacts/${result.id}`)
  ).json();
  await page
    .locator(".artifact-list button")
    .filter({ hasText: item.title })
    .click();
  await page.getByRole("heading", { name: item.title, exact: true }).waitFor();
  await page.locator(".execution-result").waitFor();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(200);
  assert(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  );
  await page.screenshot({ path: `${folder}/execution-mobile.png` });
  report.checks.push(
    "Persisted preflight reopens and 390px page has no horizontal overflow",
  );
  assert.deepEqual(report.errors, []);
} catch (error) {
  report.failure = String(error);
  await page.screenshot({ path: `${folder}/execution-failure.png` });
  throw error;
} finally {
  await writeFile(
    `${folder}/execution-browser.json`,
    JSON.stringify(report, null, 2),
  );
  await browser.close();
  console.log(JSON.stringify(report, null, 2));
}
