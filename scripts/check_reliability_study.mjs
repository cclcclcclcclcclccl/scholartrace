import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import path from 'node:path';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
const {chromium}=createRequire(import.meta.url)('C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const folder='artifacts/reliability-study',base=path.resolve('evaluation/reliability_study');const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});const report={checks:[],errors:[],notice:'Automated UI check, never human timing evidence'};page.on('pageerror',e=>report.errors.push(String(e)));
await mkdir(folder,{recursive:true});
try{
 await page.goto(pathToFileURL(path.join(base,'human-study.html')).href);await page.setViewportSize({width:1440,height:1000});
 const hiddenData=JSON.parse(await page.locator('#data').textContent());assert.equal(hiddenData.cases.length,24);assert.ok(hiddenData.cases.every(c=>!('expected'in c)));
 await page.locator('#participant').fill('UI_AUTOMATED_ONLY');await page.locator('#consent').check();await page.locator('#begin').click();await page.locator('#startTrial').click();await page.screenshot({path:folder+'/study-tool.png',fullPage:false});
 for(let i=0;i<24;i++){
  if(i>0)await page.locator('#startTrial').click();await page.locator('[data-answer="unclear"]').click();await page.locator('#reason').fill('自动界面验收，不是真人判断或时间证据');await page.locator('#submit').click();
 }
 await page.locator('#done').waitFor({state:'visible'});const dl=page.waitForEvent('download');await page.locator('#export').click();await(await dl).saveAs(folder+'/UI_AUTOMATED_ONLY.json');const result=JSON.parse(await readFile(folder+'/UI_AUTOMATED_ONLY.json','utf8'));assert.ok(result.complete);assert.equal(result.results.length,24);assert.equal(result.results.filter(r=>r.condition==='manual').length,12);assert.equal(new Set(result.results.map(r=>r.case_id)).size,24);assert.ok(result.results.every(r=>r.wall_ms>=r.active_ms&&r.active_ms>=0));
 await page.reload();await page.locator('#participant').fill('UI_AUTOMATED_ONLY');await page.locator('#consent').check();await page.locator('#begin').click();await page.locator('#done').waitFor({state:'visible'});report.checks.push('对照工具24题无重复，12/12分组，开始计时、选择、理由、JSON导出和刷新恢复通过；答案标签不进入参与者数据');assert.deepEqual(report.errors,[]);
}catch(e){report.failure=String(e);process.exitCode=1;await page.screenshot({path:folder+'/ui-failure.png'});}finally{await writeFile(folder+'/proof-ui-report.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));await browser.close();}
