import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {readFile, writeFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
const {chromium}=createRequire(import.meta.url)('C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const folder='artifacts/research-polish-20261021';
const report={notice:'Guide navigation and replayed real-answer UI checks, not new model inference or user study.',checks:[],errors:[],complete:false};
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try {
  const page=await browser.newPage({viewport:{width:1280,height:900}});
  page.on('pageerror',e=>report.errors.push(String(e)));
  await page.goto(pathToFileURL(resolve(`${folder}/演示指南.html`)).href);
  for(let index=1;index<=8;index++) {
    assert.equal(await page.locator('.step:visible').count(),1);
    assert.ok((await page.locator('.step:visible small').innerText()).includes(`步骤 ${index} / 8`));
    if(index<8) await page.getByRole('button',{name:'下一步',exact:true}).click();
  }
  assert.ok(await page.getByRole('button',{name:'下一步',exact:true}).isDisabled());
  await page.getByRole('button',{name:'回到开头'}).click();
  assert.ok(await page.getByRole('button',{name:'上一步',exact:true}).isDisabled());
  report.checks.push('All eight guide steps, endpoint buttons and reset');
  await page.screenshot({path:`${folder}/guide-desktop.png`,fullPage:true});
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.screenshot({path:`${folder}/guide-mobile.png`,fullPage:true});
  report.checks.push('Guide fits mobile width');
  const answer=JSON.parse(await readFile(`${folder}/workflow/second-answer-1.json`,'utf8'));
  let sent=0;
  await page.route('**/api/ask',route=>{sent++;return route.fulfill({json:answer});});
  await page.goto('http://127.0.0.1:8767/');
  await page.getByRole('dialog').waitFor();await page.keyboard.press('Escape');
  const fixture=JSON.parse(await readFile(`${folder}/workflow/fixture.json`,'utf8'));
  await page.getByLabel('选择阅读文献').selectOption(fixture.papers[0].id);
  await page.getByLabel('研究问题',{exact:true}).fill(answer.answer_checklist.question);
  await page.getByLabel('研究问题',{exact:true}).press('Enter');
  const checks=page.locator('.answer-checklist');await checks.waitFor();
  await checks.getByText(/展开相关回答与来源/).first().click();
  await checks.getByRole('button',{name:'核对清单原文 1',exact:true}).first().click();
  assert.equal(await page.getByRole('spinbutton').getAttribute('aria-valuenow'),'2');
  await checks.getByRole('button',{name:'补问：批大小',exact:true}).click();
  assert.equal(sent,1);
  assert.equal(await page.getByLabel('检索范围',{exact:true}).inputValue(),'current');
  report.checks.push('Replayed checklist source jump and followup do not auto-send');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await checks.screenshot({path:`${folder}/checklist-mobile.png`});
  report.checks.push('Checklist source details fit mobile width');
  assert.deepEqual(report.errors,[]);report.complete=true;
}catch(error){report.failure=String(error);throw error;}
finally{await writeFile(`${folder}/guide-browser.json`,JSON.stringify(report,null,2));await browser.close();console.log(JSON.stringify(report,null,2));}
