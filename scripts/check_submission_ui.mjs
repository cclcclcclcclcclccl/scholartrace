import {createRequire} from 'node:module';
import {writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const {chromium}=createRequire(import.meta.url)('C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const b=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});const p=await b.newPage({viewport:{width:1440,height:1000}});const report={checks:[],errors:[]};p.on('pageerror',e=>report.errors.push(String(e)));
try{
 await p.goto('http://127.0.0.1:8765');await p.getByRole('dialog').waitFor();await p.keyboard.press('Escape');report.checks.push('首次访问教程');
 const jump=p.getByLabel('当前页码');await jump.fill('');assert.equal(await jump.inputValue(),'');await jump.fill('7');await jump.press('Enter');await p.waitForFunction(()=>document.querySelector('.paper-stage')?.getAttribute('aria-busy')==='false');assert.equal(await jump.inputValue(),'7');report.checks.push('页码允许删空后跳到7');
 await p.getByLabel('研究问题').fill('未发送的演示检查');await p.getByLabel('研究问题').press('Shift+Enter');assert.match(await p.getByLabel('研究问题').inputValue(),/\n/);report.checks.push('Shift+Enter换行');
 await p.getByRole('button',{name:'版本复核',exact:true}).click();await p.getByRole('button',{name:'版本复核使用说明',exact:true}).click();await p.getByRole('dialog').waitFor();report.checks.push('复核模块帮助');await p.keyboard.press('Escape');
 await p.setViewportSize({width:390,height:844});assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await p.screenshot({path:'artifacts/submission-20261018/mobile-final.png',fullPage:true});report.checks.push('390px复核页面无横向溢出');
 const h=await(await p.request.get('http://127.0.0.1:8765/api/health')).json();report.health=h;assert.equal(h.model_available,true);assert.deepEqual(report.errors,[]);
}finally{await writeFile('artifacts/submission-20261018/final-browser.json',JSON.stringify(report,null,2));await b.close();console.log(report.checks);}
