import { createRequire } from "node:module";
import { readFile, writeFile } from "node:fs/promises";
import assert from "node:assert/strict";

const { chromium } = createRequire(import.meta.url)(
  process.env.CODEX_BROWSER_MODULE ||
    "C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright",
);
const browser = await chromium.launch({
  executablePath:
    process.env.CHROME_PATH ||
    "C:/Program Files/Google/Chrome/Application/chrome.exe",
  headless: true,
});
const page = await browser.newPage({
  viewport: { width: 1512, height: 1080 },
  baseURL: "http://127.0.0.1:8765",
});
const folder = "artifacts/research-round3";
const attempt = process.env.REVISION_ATTEMPT || "first";
const report = { checks: [], errors: [] };
const exactTitle = (title) =>
  new RegExp(
    "^writing\\s*" + title.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "$",
  );
page.on("pageerror", (error) => report.errors.push(String(error)));
try {
  const prior = JSON.parse(
    await readFile("artifacts/product-audit/writing-final-live.json", "utf8"),
  );
  const existing = process.env.REVISION_JOB_ID
    ? await (
        await page.request.get(`/api/jobs/${process.env.REVISION_JOB_ID}`)
      ).json()
    : null;
  const source = await (
    await page.request.get(
      `/api/artifacts/${existing?.result.revision_audit.source_id || prior.result.id}`,
    )
  ).json();
  await page.goto("/");
  await page.getByRole("dialog").waitFor();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "任务与成果", exact: true }).click();
  await page
    .locator(".artifact-list button")
    .filter({ hasText: exactTitle(source.title) })
    .click();
  await page
    .getByRole("heading", { name: source.title, exact: true })
    .waitFor();
  let job = existing;
  if (!job) {
    const submitted = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/jobs") &&
        response.request().method() === "POST",
    );
    await page
      .getByRole("button", { name: "复核并生成独立修订稿", exact: true })
      .click();
    const response = await submitted;
    assert(response.ok());
    job = await response.json();
    assert.equal(job.payload.artifact_id, source.id);
  }
  report.job_id = job.id;
  report.source_id = source.id;
  console.log(
    existing
      ? "Rechecking existing real revision:"
      : "Real local model revision submitted through browser:",
    job.id,
  );
  let result;
  for (let i = 0; i < 150; i++) {
    result = await (await page.request.get(`/api/jobs/${job.id}`)).json();
    if (["completed", "failed", "cancelled"].includes(result.state)) break;
    await page.waitForTimeout(2000);
  }
  await writeFile(
    `${folder}/proposal-revision-${attempt}.json`,
    JSON.stringify(result, null, 2),
  );
  assert.equal(result.state, "completed", result.error);
  assert.notEqual(result.result.id, source.id);
  assert.equal(result.result.revision_audit.source_id, source.id);
  assert.deepEqual(
    result.result.revision_audit.original_proposal,
    source.content.proposal,
  );
  const after = await (
    await page.request.get(`/api/artifacts/${source.id}`)
  ).json();
  assert.deepEqual(after.content, source.content);
  assert.deepEqual(result.result.sections, source.content.sections);
  assert.deepEqual(result.result.references, source.content.references || []);
  assert.equal(
    result.result.proposal.introduction,
    source.content.proposal.introduction,
  );
  report.checks.push(
    existing
      ? "Rechecked actual source identity, original proposal and source preservation for existing real model job"
      : "Actual UI submits durable revision job; original content and all source sections/references preserved",
  );
  await page
    .getByRole("button", { name: "刷新任务和文献库", exact: true })
    .click();
  await page
    .locator(".artifact-list button")
    .filter({ hasText: exactTitle(result.result.title) })
    .click();
  await page
    .getByRole("heading", { name: result.result.title, exact: true })
    .waitFor();
  await page.getByText("核对这次修订的原稿与检查记录", { exact: true }).click();
  await page.getByText("修订前的拟议方法", { exact: true }).waitFor();
  await page
    .locator(".proposal-revision")
    .screenshot({ path: `${folder}/proposal-revision-ui.png` });
  report.checks.push(
    "Saved revision reopens with original proposal and before/after checks",
  );
  const experiments = JSON.parse(
    await readFile(`${folder}/browser-report.json`, "utf8"),
  );
  const protocol = await (
    await page.request.get(`/api/artifacts/${experiments.protocol_id}`)
  ).json();
  await page
    .locator(".artifact-list button")
    .filter({ hasText: protocol.title })
    .first()
    .click();
  const card = page.locator(".artifact-result .protocol-editor");
  if (!(await card.evaluate((element) => element.open)))
    await card.locator(":scope > summary").click();
  assert.equal(
    await card.getByLabel("对照基线", { exact: true }).inputValue(),
    protocol.content.protocol.baseline,
  );
  await card
    .getByText(`当前保存版本：第 ${protocol.content.revision} 版`, {
      exact: true,
    })
    .waitFor();
  report.checks.push(
    "Reopening an edited protocol loads latest saved revision and fields",
  );
  assert.deepEqual(report.errors, []);
} catch (error) {
  report.failure = String(error);
  await page.screenshot({ path: `${folder}/revision-ui-failure.png` });
  throw error;
} finally {
  await writeFile(
    `${folder}/revision-browser-${attempt}.json`,
    JSON.stringify(report, null, 2),
  );
  await browser.close();
  console.log(JSON.stringify(report, null, 2));
}
