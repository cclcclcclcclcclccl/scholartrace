import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {writeFile,readFile} from 'node:fs/promises';
import {ownedProcess} from './runtime.mjs';
const {chromium}=createRequire(import.meta.url)('C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const folder='artifacts/discovery-history',base='http://127.0.0.1:8765';
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});page.setDefaultTimeout(90000);
const report={checks:[],errors:[]};let searches=0;
page.on('pageerror',e=>report.errors.push(String(e)));
page.on('request',r=>{if(r.url().endsWith('/api/discover/search')||r.url().endsWith('/api/discover/related'))searches++;});
async function discover(){await page.getByRole('button',{name:'论文发现',exact:true}).click();await page.getByLabel('检索方式').waitFor();}
async function restore(label){const details=page.locator('.discovery-history');if((await details.getAttribute('open'))===null)await details.locator('summary').click();const row=details.locator('.discovery-history-row').filter({hasText:label}).first();await row.getByRole('button',{name:'恢复这次发现'}).click();await page.locator('.discovery-snapshot').waitFor();}
try{
 let ready=false;for(let i=0;i<40;i++){try{if((await page.request.get(base+'/api/health',{timeout:2000})).ok()){ready=true;break;}}catch{}await page.waitForTimeout(500);}assert.ok(ready);
 await page.goto(base);await page.getByRole('dialog').waitFor();await page.keyboard.press('Escape');await discover();
 await page.getByLabel('检索方式').selectOption('identifier');const query='https://doi.org/10.1038/nature14539';await page.getByLabel('论文检索词',{exact:true}).fill(query);
 let done=page.waitForResponse(r=>r.url().endsWith('/api/discover/search'));
 await page.getByLabel('论文检索词',{exact:true}).press('Enter');assert.equal((await done).status(),200);await page.locator('.remote-paper').first().waitFor();
 const records=await (await page.request.get(base+'/api/discover/history')).json();report.search_record=records.items[0];assert.equal(records.items[0].label,query);
 await page.getByRole('button',{name:'文献管理',exact:true}).click();await discover();
 let count=searches;await restore(query);assert.equal(await page.getByLabel('论文检索词',{exact:true}).inputValue(),query);assert.ok((await page.locator('.remote-paper').first().innerText()).includes('Deep learning'));assert.equal(searches,count);report.checks.push('离开页面后恢复查询和真实 DOI 结果，不重新搜索');
 await page.reload();await discover();count=searches;await restore(query);assert.equal(searches,count);report.checks.push('刷新后记录仍存在，恢复不联网');
 const download=page.waitForEvent('download');await page.locator('.discovery-history-row').filter({hasText:query}).first().getByRole('button',{name:'导出记录 JSON'}).click();await (await download).saveAs(`${folder}/export.json`);const saved=JSON.parse(await readFile(`${folder}/export.json`,'utf8'));assert.equal(saved.spec.query,query);assert.equal(saved.result[0].doi,'10.1038/nature14539');assert.ok(!('view' in saved));report.checks.push('导出原始条件、时间和结果，未把当前显示结果覆盖历史');
 done=page.waitForResponse(r=>r.url().endsWith('/api/discover/search'));await page.getByRole('button',{name:'按记录条件重新检索'}).click();const fresh=await done;assert.equal(fresh.request().postDataJSON().force,true);assert.equal(fresh.status(),200);await page.locator('.discovery-snapshot').waitFor({state:'hidden'});report.checks.push('显式重新检索使用 force，解除历史显示状态');
 const docs=await (await page.request.get(base+'/api/documents')).json();const seed=docs.find(d=>d.arxiv_id==='1706.03762'&&d.version===7);assert.ok(seed);
 await page.locator('.discovery-seed summary').click();await page.getByLabel('关联种子论文').selectOption(seed.id);done=page.waitForResponse(r=>r.url().endsWith('/api/discover/related'));await page.getByRole('button',{name:'查找相关文章',exact:true}).click();const related=await (await done).json();assert.ok(related.local.length);
 const all=await (await page.request.get(base+'/api/discover/history')).json();report.related_record=all.items[0];assert.equal(all.items[0].kind,'related');
 const jobs=await (await page.request.get(base+'/api/jobs')).json();assert.ok(!jobs.some(j=>['running','queued','pending'].includes(j.state)));assert.ok(ownedProcess('server',true));
 let healthy=false;for(let i=0;i<40;i++){try{const r=await page.request.get(base+'/api/health',{timeout:2000});if(r.ok()){healthy=true;break;}}catch{}await page.waitForTimeout(500);}assert.ok(healthy);
 await page.reload();await discover();count=searches;await restore(seed.title);assert.equal(searches,count);assert.equal(await page.getByLabel('关联种子论文').inputValue(),seed.id);assert.ok((await page.locator('.discovery-related').innerText()).includes('库内相关论文'));report.checks.push('真实服务重启后恢复关联探索，保留种子和库内结果');
 await page.screenshot({path:`${folder}/desktop.png`,fullPage:true});await page.setViewportSize({width:390,height:844});await page.screenshot({path:`${folder}/mobile.png`,fullPage:true});report.mobile=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth}));assert.ok(report.mobile.scroll<=report.mobile.width+1);assert.deepEqual(report.errors,[]);
}catch(e){report.failure=String(e);await page.screenshot({path:`${folder}/failure.png`,fullPage:true});process.exitCode=1;}finally{await writeFile(`${folder}/browser-report.json`,JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));await browser.close();}
