import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {writeFile} from 'node:fs/promises';
const {chromium}=createRequire(import.meta.url)('C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const folder=process.env.SCHOLARTRACE_CHECK_FOLDER || 'artifacts/transfer-comparison-20261020',base='http://127.0.0.1:8765';
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
const report={errors:[],notice:'正式站点只读检查；不向正式文库写入测试笔记或问答。'};
try{
 const page=await browser.newPage({viewport:{width:390,height:844}});
 page.on('pageerror',e=>report.errors.push(String(e)));
 assert.equal((await page.goto(base)).status(),200);
 await page.getByRole('dialog').waitFor();await page.keyboard.press('Escape');
 await page.getByLabel('选择阅读文献').selectOption('c464f839fb8d59f7fde92f9b4caa67c2d1f2f196b88f93fb60502249df0aaef7');
 await page.getByRole('spinbutton').fill('');await page.getByRole('spinbutton').fill('7');await page.getByRole('spinbutton').press('Enter');
 assert.equal(await page.getByRole('spinbutton').getAttribute('aria-valuenow'),'7');
 await page.getByLabel('回车键行为').selectOption('newline');await page.getByLabel('回车键行为').selectOption('send');
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 await page.screenshot({path:`${folder}/main-mobile.png`});
 await page.setViewportSize({width:1440,height:1000});
 await page.screenshot({path:`${folder}/main-desktop.png`});
 const health=await(await page.request.get(`${base}/api/health`)).json();assert.ok(health.model_available);
 assert.deepEqual(report.errors,[]);report.complete=true;report.mobile_fits=true;report.health=health;
}finally{await writeFile(`${folder}/main-browser.json`,JSON.stringify(report,null,2));await browser.close();}
