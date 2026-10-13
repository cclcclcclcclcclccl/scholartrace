import { createRequire } from "node:module";
import { writeFile, mkdir } from "node:fs/promises";
import assert from "node:assert/strict";
const { chromium } = createRequire(import.meta.url)(
  process.env.CODEX_BROWSER_MODULE ||
    "C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright",
);
const root =
  process.env.SCHOLARTRACE_QA_ARTIFACTS ||
  `artifacts/quality-round7/browser-${Date.now()}`;
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
const question =
  "请分别回答：ViT-Base 在表 1 中的层数、隐藏宽度和参数量是多少？论文有没有报告 ViT-H/14 使用随机种子 42 的那一次独立训练的 ImageNet 准确率？后者不能用汇总结果代替，缺证据也请保留前一项的回答。";
try {
  await page.goto("/");
  await page.getByRole("dialog").waitFor();
  await page.keyboard.press("Escape");
  await page
    .getByRole("textbox", { name: "筛选文献" })
    .fill("2010.11929v2.pdf");
  await page.locator(".document-item").first().click();
  const pending = page.waitForResponse(
    (r) => r.url().endsWith("/api/ask") && r.request().method() === "POST",
    { timeout: 180000 },
  );
  await page.getByRole("textbox", { name: "研究问题" }).fill(question);
  await page.getByRole("textbox", { name: "研究问题" }).press("Enter");
  const response = await pending;
  assert(response.ok());
  report.answer = await response.json();
  assert.equal(report.answer.subquestions.length, 2);
  const first = report.answer.subquestions[0];
  const second = report.answer.subquestions[1];
  assert.equal(first.status, "reviewed_answer");
  assert.equal(second.status, "unresolved");
  const coverage = page.locator(".results .answer-coverage");
  await coverage.waitFor();
  assert.equal(await coverage.locator("li").count(), 2);
  assert((await coverage.innerText()).includes(second.question));
  await coverage.screenshot({ path: `${root}/coverage-desktop.png` });
  report.checks.push(
    "Real local-model partial answer preserves known specification and shows unresolved per-seed measurement",
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await coverage.screenshot({ path: `${root}/coverage-mobile.png` });
  assert(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  );
  report.checks.push(
    "390px coverage panel has no page-wide horizontal overflow",
  );
  await page.setViewportSize({ width: 1512, height: 1080 });
  const artifact = report.answer.artifact_id;
  assert(artifact);
  const saved = await (
    await page.request.get(`/api/artifacts/${artifact}`)
  ).json();
  assert.deepEqual(
    saved.content.sections[0].subquestions,
    report.answer.subquestions,
  );
  const download = await page.request.get(
    `/api/artifacts/${artifact}/export?format=md`,
  );
  assert(download.ok());
  const markdown = await download.text();
  assert(
    markdown.includes(first.question) && markdown.includes(second.question),
  );
  assert(markdown.includes(second.reason));
  await writeFile(`${root}/partial-answer-export.md`, markdown);
  await page.getByRole("button", { name: "任务与成果", exact: true }).click();
  await page.getByRole("button").filter({ hasText: question }).first().click();
  await page.locator(".artifact-result .answer-coverage").waitFor();
  assert.equal(
    await page.locator(".artifact-result .answer-coverage li").count(),
    2,
  );
  const candidate = page
    .locator(".artifact-result .answer-coverage")
    .getByRole("button", { name: /查看候选原文/ })
    .first();
  await candidate.waitFor();
  const raw = page.locator(".artifact-result .claim-source").first();
  assert.equal(await raw.getAttribute("open"), null);
  await raw.locator("summary").click();
  assert.equal(
    await raw.locator("blockquote").innerText(),
    report.answer.model_answer[0].quote,
  );
  await raw.locator("summary").click();
  report.checks.push(
    "Original citations collapse by default and expand without losing text; unresolved items offer source candidates",
  );
  await page
    .locator(".artifact-result")
    .screenshot({ path: `${root}/coverage-reopened.png` });
  const candidateLabel = await candidate.innerText();
  const candidatePage = Number(candidateLabel.match(/第\s*(\d+)\s*页/)[1]);
  await candidate.click();
  await page.getByRole("spinbutton", { name: "当前页码" }).waitFor();
  assert.equal(
    Number(
      await page.getByRole("spinbutton", { name: "当前页码" }).inputValue(),
    ),
    candidatePage,
  );
  report.checks.push(
    "Unresolved candidate source opens the matching PDF page from a saved artifact",
  );
  report.checks.push(
    "Persisted partial answer reopens with the same coverage and exports missing items to Markdown",
  );
  assert.deepEqual(report.errors, []);
} catch (e) {
  report.failure = String(e);
  await page.screenshot({ path: `${root}/coverage-failure-${Date.now()}.png` });
  throw e;
} finally {
  await writeFile(
    `${root}/coverage-browser-${Date.now()}.json`,
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
