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
  viewport: { width: 1440, height: 1000 },
  baseURL: "http://127.0.0.1:8766",
});
const report = {
  notice:
    "Real browser and real local-model API, isolated database on port 8766; not independent accuracy evaluation.",
  checks: [],
  errors: [],
};
page.on("pageerror", (e) => report.errors.push(String(e)));
const question =
  "CLIP 预训练数据的规模和组成是什么？请区分图文对数量与 ImageNet 训练图片数量。";
try {
  await page.goto("/");
  await page.getByRole("dialog").waitFor();
  await page.keyboard.press("Escape");
  await page.getByLabel("筛选文献").fill("2103.00020v1.pdf");
  await page.locator(".document-item").first().click();
  const pending = page.waitForResponse(
    (r) => r.url().endsWith("/api/ask") && r.request().method() === "POST",
    { timeout: 300000 },
  );
  await page.getByLabel("研究问题").fill(question);
  await page.getByLabel("研究问题").press("Enter");
  const response = await pending;
  assert(response.ok());
  report.answer = await response.json();
  const partial = report.answer.subquestions.find(
    (x) => x.status === "reviewed_answer" && x.omitted_candidate_count > 0,
  );
  assert(partial, "Expected a real partly retained candidate set");
  const row = page
    .locator(".results .answer-coverage li")
    .filter({ hasText: partial.question })
    .first();
  await row.waitFor();
  assert((await row.innerText()).includes("未进入最终回答"));
  await row.getByRole("button", { name: "单独追问此项" }).click();
  assert.equal(
    await page.getByLabel("研究问题").inputValue(),
    partial.question,
  );
  report.checks.push(
    "Partly answered item shows omission notice and prepares exact follow-up",
  );
  const candidate = row.getByRole("button", { name: /查看候选原文/ }).first();
  const label = await candidate.innerText();
  const target = Number(label.match(/第\s*(\d+)\s*页/)[1]);
  await candidate.click();
  assert.equal(Number(await page.getByLabel("当前页码").inputValue()), target);
  report.checks.push("Partly answered item opens candidate PDF page");
  const saved = await (
    await page.request.get("/api/artifacts/" + report.answer.artifact_id)
  ).json();
  assert.deepEqual(
    saved.content.sections[0].subquestions,
    report.answer.subquestions,
  );
  const exported = await page.request.get(
    "/api/artifacts/" + report.answer.artifact_id + "/export?format=md",
  );
  assert(exported.ok());
  const markdown = await exported.text();
  assert(markdown.includes(partial.reason));
  await writeFile(
    "artifacts/improvement-v8/partial-answer-export.md",
    markdown,
  );
  report.checks.push(
    "Saved artifact and Markdown retain omitted-candidate explanation",
  );
  await page
    .locator(".results")
    .screenshot({ path: "artifacts/improvement-v8/partial-desktop.png" });
  await page.setViewportSize({ width: 390, height: 844 });
  assert(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  );
  await row.screenshot({ path: "artifacts/improvement-v8/partial-mobile.png" });
  report.checks.push("390px page has no horizontal overflow");
  assert.deepEqual(report.errors, []);
} catch (e) {
  report.failure = String(e);
  await page.screenshot({
    path: "artifacts/improvement-v8/browser-failure.png",
  });
  throw e;
} finally {
  await writeFile(
    "artifacts/improvement-v8/browser.json",
    JSON.stringify(report, null, 2),
  );
  await browser.close();
  console.log(
    JSON.stringify({ checks: report.checks, failure: report.failure }),
  );
}
