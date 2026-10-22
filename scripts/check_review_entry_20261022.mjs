import {createRequire} from 'node:module';
import {readFile,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const {chromium}=createRequire(import.meta.url)('C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const base=(await readFile('artifacts/public-review-20261021/url.txt','utf8')).trim();
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try {
 const page=await browser.newPage();
 const fixed='https://cclcclcclcclcclccl.github.io/scholartrace/';
 await page.goto(fixed+'?verify='+Date.now(),{timeout:60000});
 await page.waitForFunction(expected=>document.querySelector('#demo')?.href.replace(/\/$/,'')===expected,base,{timeout:60000});
 assert.match(await page.title(),/科研证据/);
 const config=await (await page.request.get(fixed+'runtime.json?t='+Date.now())).json();
 assert.equal(config.url,base);
 await page.route('**/runtime.json*',route=>route.abort());
 await page.reload();
 await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('暂时无法'));
 assert.equal((await page.locator('#demo').getAttribute('href')).replace(/\/$/,''),base);
 await page.screenshot({path:'artifacts/public-recovery-20261022/fixed-entry.png',fullPage:true});
 await page.goto(base,{timeout:60000});assert.match(await page.title(),/墨衡/);
 const result={checked_at:new Date().toISOString(),fixed,url:base,checks:['Published Pages points to current endpoint','Updated HTML fallback works when runtime request fails','Public workbench loads'],complete:true};
 await writeFile('artifacts/public-recovery-20261022/fixed-entry-check.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
}finally{await browser.close();}
