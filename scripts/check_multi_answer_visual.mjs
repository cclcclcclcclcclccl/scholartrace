// Layout-only replay of a saved REAL browser response. No new model inference.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {readFile,writeFile} from 'node:fs/promises';
const {chromium}=createRequire(import.meta.url)('C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const folder='artifacts/quality-round8/browser';
const answer=JSON.parse(await readFile(`${folder}/answer.json`,'utf8'));
const report={notice:'Layout replay of previously recorded real local-model browser answer; not a new inference check.',errors:[]};
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
try{
 const p=await browser.newPage({viewport:{width:1440,height:1000}});
 p.on('pageerror',e=>report.errors.push(String(e)));
 await p.route('**/api/ask',route=>route.fulfill({json:answer}));
 await p.goto('http://127.0.0.1:8765/');
 await p.getByRole('dialog').waitFor();await p.keyboard.press('Escape');
 await p.getByLabel('研究问题',{exact:true}).fill('查看已记录的复合问题回答，用于布局检查');
 await p.getByLabel('研究问题',{exact:true}).press('Enter');
 const cards=p.locator('.paper-answer');await cards.first().waitFor();
 await cards.nth(1).getByRole('button',{name:'核对本篇原文',exact:true}).first().click();
 await cards.first().getByRole('button',{name:'单独追问此项',exact:true}).click();
 await p.locator('.paper-stage[aria-busy="false"]').waitFor();
 await p.waitForFunction(()=>{
   const c=document.querySelector('.paper-sheet canvas');
   if(!c||!c.width)return false;
   const data=c.getContext('2d').getImageData(2,2,1,1).data;
   return data[0]>230&&data[1]>230&&data[2]>230&&data[3]>230;
 });
 await p.screenshot({path:`${folder}/final-desktop.png`});
 report.pdfRendered=true;
 await p.setViewportSize({width:390,height:844});
 await cards.first().scrollIntoViewIfNeeded();
 assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 report.fontSize=await cards.first().locator('.result-note').evaluate(e=>getComputedStyle(e).fontSize);
 assert.equal(report.fontSize,'12px');
 await cards.first().screenshot({path:`${folder}/final-mobile-card.png`});
 assert.deepEqual(report.errors,[]);report.passed=true;
}finally{await writeFile(`${folder}/visual-replay-report.json`,JSON.stringify(report,null,2));console.log(JSON.stringify(report));await browser.close();}
