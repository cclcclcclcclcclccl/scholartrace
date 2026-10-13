import { createRequire } from "node:module";
import { writeFile, mkdir } from "node:fs/promises";
import assert from "node:assert/strict";
const { chromium } = createRequire(import.meta.url)(
  process.env.CODEX_BROWSER_MODULE ||
    "C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright",
);
const root = "artifacts/quality-round5";
await mkdir(root, { recursive: true });
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
async function json(response) {
  assert(response.ok(), await response.text());
  return response.json();
}
try {
  const spec = {
    title: "浏览器验收：历史设计绑定（示例）",
    hypothesis: "验证旧测量可正确绑定执行时的设计版本",
    task: "other",
    dataset: "浏览器合成示例，不是科研实测",
    split: "固定示例输入",
    baseline: "第一版对照",
    variable: "示例方法",
    controls: "固定输入与运行标识",
    metric: "loss",
    direction: "lower",
    criterion: "按所选版本校验并保留原始数据",
    seeds: [1, 2],
    resources: "本地示例",
    failure: "保留失败输出",
  };
  const protocol = await json(
    await page.request.post("/api/experiments/protocols", { data: spec }),
  );
  report.protocol_id = protocol.id;
  const v2 = {
    ...spec,
    metric: "score",
    baseline: "第二版对照",
    seeds: [11, 23, 47],
  };
  await json(
    await page.request.put(`/api/experiments/protocols/${protocol.id}`, {
      data: { revision: 1, protocol: v2 },
    }),
  );
  await page.goto("/");
  await page.getByRole("dialog").waitFor();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "科研工作室", exact: true }).click();
  const lab = page.locator(".measurement-lab");
  await lab.locator(":scope > summary").click();
  await lab
    .getByLabel("关联实验设计", { exact: true })
    .selectOption(protocol.id);
  const versions = lab.getByLabel("实际执行的设计版本");
  await versions.locator('option[value="1"]').waitFor({ state: "attached" });
  assert.equal(await versions.inputValue(), "2");
  await versions.selectOption("1");
  await lab.getByText(/即将绑定第 1 版：指标 loss/).waitFor();
  await lab
    .getByLabel("重复实验 CSV", { exact: true })
    .fill("method,seed,loss\nA,1,2\nA,2,4");
  await lab.getByLabel("实测指标列").fill("loss");
  await lab.getByLabel("统计数据类型").selectOption("example");
  await lab.getByLabel("统计标题").fill("浏览器验收：历史第一版统计（示例）");
  async function submit() {
    const pending = page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/experiments/analyze") &&
        r.request().method() === "POST",
    );
    await lab
      .getByRole("button", { name: "计算并保存重复实验统计", exact: true })
      .click();
    const result = await json(await pending);
    await lab.locator(".measurement-result img").waitFor();
    await lab
      .locator(".measurement-result img")
      .evaluate((img) => img.decode());
    return result;
  }
  const historical = await submit();
  report.historical_measurement = historical.id;
  assert.equal(historical.protocol_snapshot.revision, 1);
  assert.equal(historical.protocol_snapshot.protocol.baseline, spec.baseline);
  assert.equal(historical.summary[0].mean, 3);
  assert(historical.warnings.some((w) => w.includes("历史设计")));
  assert(!historical.warnings.some((w) => /种子集合不一致|指标列名/.test(w)));
  report.checks.push(
    "Select revision 1 with its own metric/seeds while latest is revision 2; preview and persisted snapshot agree",
  );
  await lab.screenshot({ path: `${root}/historical-version-desktop.png` });
  await versions.selectOption("2");
  await lab
    .getByRole("button", { name: "载入示例（非实验结果）", exact: true })
    .click();
  await lab
    .getByLabel("统计标题")
    .fill("浏览器验收：并发修改仍绑定第二版（示例）");
  await json(
    await page.request.put(`/api/experiments/protocols/${protocol.id}`, {
      data: {
        revision: 2,
        protocol: { ...v2, baseline: "第三版对照", seeds: [101, 102] },
      },
    }),
  );
  const concurrent = await submit();
  report.concurrent_measurement = concurrent.id;
  assert.equal(concurrent.protocol_snapshot.revision, 2);
  assert.deepEqual(concurrent.protocol_snapshot.protocol.seeds, [11, 23, 47]);
  assert(concurrent.warnings.some((w) => w.includes("当前最新版为第 3 版")));
  assert(!concurrent.warnings.some((w) => w.includes("种子集合不一致")));
  report.checks.push(
    "Saving after another editor creates revision 3 retains explicitly selected revision 2",
  );
  await lab
    .getByRole("button", { name: "刷新实验设计列表", exact: true })
    .click();
  await versions.locator('option[value="3"]').waitFor({ state: "attached" });
  assert.equal(await versions.inputValue(), "3");
  report.checks.push(
    "Refresh retrieves latest revision and keeps historical choices available",
  );
  const bundle = await page.request.get(
    `/api/experiments/${historical.id}/files/bundle.zip`,
  );
  assert(bundle.ok());
  await writeFile(`${root}/historical-reproduction.zip`, await bundle.body());
  const saved = await json(
    await page.request.get(`/api/artifacts/${historical.id}`),
  );
  assert.deepEqual(
    saved.content.protocol_snapshot,
    historical.protocol_snapshot,
  );
  await page.getByRole("button", { name: "任务与成果", exact: true }).click();
  await page
    .getByRole("button")
    .filter({ hasText: "浏览器验收：历史第一版统计（示例）" })
    .first()
    .click();
  await page.locator(".measurement-result img").waitFor();
  await page
    .locator(".measurement-result")
    .getByText(/第 1 版/)
    .waitFor();
  report.checks.push(
    "Persisted historical result reopens and reproduction bundle downloads without rewriting its protocol",
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator(".measurement-result").scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${root}/historical-version-mobile.png` });
  assert(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  );
  report.checks.push(
    "390px result layout has no page-wide horizontal overflow",
  );
  assert.deepEqual(report.errors, []);
} catch (e) {
  report.failure = String(e);
  await page.screenshot({
    path: `${root}/history-ui-failure-${Date.now()}.png`,
  });
  throw e;
} finally {
  await writeFile(
    `${root}/history-browser-${Date.now()}.json`,
    JSON.stringify(report, null, 2),
  );
  await browser.close();
  console.log(JSON.stringify(report, null, 2));
}
