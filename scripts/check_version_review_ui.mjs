import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {readFile,writeFile} from 'node:fs/promises';
const {chromium}=createRequire(import.meta.url)('C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const base='http://127.0.0.1:8765',folder='artifacts/version-review-quality';
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000}});page.setDefaultTimeout(90000);
const report={checks:[],errors:[]};page.on('pageerror',e=>report.errors.push(String(e)));
try{
 let ready=false;for(let i=0;i<40;i++){try{if((await page.request.get(base+'/api/health',{timeout:2000})).ok()){ready=true;break;}}catch{}await page.waitForTimeout(500);}assert.ok(ready);
 await page.goto(base);await page.getByRole('dialog').waitFor();await page.keyboard.press('Escape');
 const docs=await (await page.request.get(base+'/api/documents')).json();const target=docs.find(d=>d.arxiv_id==='1706.03762'&&d.version===7);
 await page.getByRole('button',{name:'版本复核',exact:true}).click();await page.getByLabel('对照版本').selectOption(target.id);
 const done=page.waitForResponse(r=>r.url().endsWith('/api/versions/audit'));
 await page.getByRole('button',{name:'检查证据变化',exact:true}).click();const response=await done;assert.equal(response.status(),200);const actual=await response.json();report.real=actual;
 await page.locator('.audit-coverage').waitFor();assert.equal(await page.locator('.audit-card').count(),actual.results.length);
 const selectors=page.locator('.review-evidence summary');assert.ok(await selectors.count()>0);
 const first=page.locator('.review-evidence').first();if((await first.getAttribute('open'))===null)await first.locator('summary').click();assert.ok((await first.innerText()).includes('旧版比较引文'));report.checks.push('真实 v1/v7 复核显示覆盖状态与实际比较引文');
 await page.screenshot({path:`${folder}/real-audit.png`,fullPage:true});
 const candidateCard=page.locator('.audit-card').filter({hasText:'代码'}).first();await candidateCard.getByRole('button',{name:/查看旧版原文/}).click();await page.locator('.paper-stage').waitFor();report.checks.push('真实旧版出处按钮进入阅读台');
 // Display-only replay of the controlled wrong-model fixture; never writes notes.
 const fixture=JSON.parse(await readFile(`${folder}/controlled-wrong-model.json`,'utf8'));
 const item={...actual.results[0],note:{...actual.results[0].note,note:'界面校验样例：GPU 数量',quote:fixture.input.note.quote},candidate:{...actual.results[0].candidate,text:fixture.input.candidate.text},status:'review_required',semantic_review:fixture.checked};
 await page.route('**/api/versions/audit',r=>r.fulfill({json:{results:[item]}}));
 await page.getByRole('button',{name:'版本复核',exact:true}).click();await page.getByLabel('对照版本').selectOption(target.id);await page.getByRole('button',{name:'检查证据变化',exact:true}).click();await page.getByText('数值差异待核对',{exact:true}).waitFor();assert.ok((await page.locator('.audit-badge').innerText()).includes('含义不确定'));assert.ok((await page.locator('.review-evidence').getAttribute('open'))!==null);report.checks.push('受控响应回放仅验证 UI：数值冲突显示不确定并展开引文，不写入用户笔记');
 await page.screenshot({path:`${folder}/controlled-display-only.png`,fullPage:true});await page.setViewportSize({width:390,height:844});report.mobile=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth}));assert.ok(report.mobile.scroll<=report.mobile.width+1);await page.screenshot({path:`${folder}/mobile-display-only.png`,fullPage:true});assert.deepEqual(report.errors,[]);
}catch(e){report.failure=String(e);await page.screenshot({path:`${folder}/failure.png`,fullPage:true});process.exitCode=1;}finally{await writeFile(`${folder}/browser-report.json`,JSON.stringify(report,null,2));console.log(JSON.stringify({checks:report.checks,errors:report.errors,failure:report.failure,mobile:report.mobile},null,2));await browser.close();}
