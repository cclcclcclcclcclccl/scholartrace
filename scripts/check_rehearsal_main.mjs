import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {writeFile} from 'node:fs/promises';
const {chromium}=createRequire(import.meta.url)('C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
const report={errors:[]};
try {
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  page.on('pageerror',e=>report.errors.push(String(e)));
  await page.goto('http://127.0.0.1:8765/');
  await page.getByRole('dialog').waitFor();await page.keyboard.press('Escape');
  await page.getByRole('button',{name:/^证据笔记/}).click();
  const panel=page.getByRole('region',{name:'组会演练'});
  await panel.getByRole('button',{name:'开始组会演练'}).click();
  await panel.getByText('组会演练怎么用？',{exact:true}).click();
  await panel.getByText(/选择1—3条证据笔记/).waitFor();
  await page.screenshot({path:'artifacts/rehearsal-20261020/main-desktop.png',fullPage:true});
  report.rehearsal=await (await page.request.get('http://127.0.0.1:8765/api/rehearsal')).json();
  report.recall=await (await page.request.get('http://127.0.0.1:8765/api/recall')).json();
  assert.equal(report.rehearsal.total,0);assert.equal(report.recall.cards.length,0);
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await panel.screenshot({path:'artifacts/rehearsal-20261020/main-mobile.png'});
  assert.deepEqual(report.errors,[]);report.loaded=true;report.mobile_fits=true;
} catch(e){report.failure=String(e.stack||e);process.exitCode=1;}
finally {await writeFile('artifacts/rehearsal-20261020/main-browser.json',JSON.stringify(report,null,2));await browser.close();}
console.log(JSON.stringify(report,null,2));
