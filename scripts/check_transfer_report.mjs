import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {writeFile} from 'node:fs/promises';
const {chromium}=createRequire(import.meta.url)('C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const folder='artifacts/transfer-comparison-20261020';
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
const report={errors:[]};
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 page.on('pageerror',e=>report.errors.push(String(e)));
 await page.goto(pathToFileURL(resolve(folder,'report.html')).href);
 assert.equal(await page.locator('article:visible').count(),25);
 await page.locator('#method').selectOption('product');
 assert.equal(await page.locator('article:visible').count(),11);
 await page.locator('#status').selectOption('partial');
 assert.equal(await page.locator('article:visible').count(),6);
 await page.locator('#search').fill('RWKV');
 assert.equal(await page.locator('article:visible').count(),2);
 await page.locator('article:visible summary').first().click();
 await page.locator('article:visible pre').first().waitFor();
 await page.screenshot({path:`${folder}/report-desktop.png`,fullPage:true});
 await page.setViewportSize({width:390,height:844});
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 await page.screenshot({path:`${folder}/report-mobile.png`,fullPage:true});
 report.complete=true;report.record_count=25;report.filters_verified=true;report.mobile_fits=true;
}finally{await writeFile(`${folder}/report-browser.json`,JSON.stringify(report,null,2));await browser.close();}
