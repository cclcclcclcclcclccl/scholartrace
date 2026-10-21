import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {mkdir,writeFile} from 'node:fs/promises';
const {chromium}=createRequire(import.meta.url)('C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const base='http://127.0.0.1:8765',folder='artifacts/stabilization';
await mkdir(folder,{recursive:true});
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});page.setDefaultTimeout(30000);
const report={checks:[],errors:[]};page.on('pageerror',e=>report.errors.push(String(e)));
const check=s=>{report.checks.push(s);console.log(s);};
try{
 let ready=false;for(let i=0;i<40;i++){try{if((await page.request.get(base+'/api/health',{timeout:2000})).ok()){ready=true;break;}}catch{}await page.waitForTimeout(500);}assert.ok(ready);
 await page.goto(base);await page.getByRole('dialog').waitFor();await page.keyboard.press('Escape');
 const projects=await(await page.request.get(base+'/api/projects')).json();assert.ok(projects.length);
 await page.goto(base+'/#project='+projects[0].id);await page.getByRole('link',{name:'下载完整成果包'}).waitFor();
 const download=page.waitForEvent('download');await page.getByRole('link',{name:'下载完整成果包'}).click();await(await download).saveAs(folder+'/project-bundle.zip');check('真实项目完整成果包下载成功');
 await page.screenshot({path:folder+'/project.png',fullPage:true});
 await page.locator('.nav-more summary').click();
 await page.getByRole('button',{name:'任务与成果',exact:true}).click();
 const first=await(await page.request.get(base+'/api/jobs-page')).json();assert.ok(first.items.length>0 && first.items.length<=50);
 let historyReplay=false;
 if(!first.next_before){historyReplay=true;const fixture=Array.from({length:55},(_,i)=>({...first.items[0],id:'history-replay-'+i,history_cursor:55-i}));await page.route('**/api/jobs-page*',r=>r.fulfill({json:r.request().url().includes('before=')?{items:fixture.slice(50),next_before:null}:{items:fixture.slice(0,50),next_before:6}}));await page.getByRole('button',{name:'刷新任务和文献库'}).click();}
 await page.getByRole('button',{name:'加载更早任务',exact:true}).waitFor();
 const older=page.waitForResponse(r=>r.url().includes('/api/jobs-page?before='));await page.getByRole('button',{name:'加载更早任务',exact:true}).click();assert.equal((await older).status(),200);check(historyReplay?'真实历史接口读取成功；受控 55 条界面回放验证加载更早任务（现有库不足 50 条）':'真实任务中心可加载更早任务');
 await page.screenshot({path:folder+'/tasks.png',fullPage:true});
 await page.getByRole('button',{name:'版本复核',exact:true}).click();
 const docs=await(await page.request.get(base+'/api/documents')).json();const target=docs.find(d=>d.arxiv_id==='1706.03762'&&d.version===7);assert.ok(target);
 await page.getByLabel('对照版本').selectOption(target.id);
 const responsePromise=page.waitForResponse(r=>r.url().endsWith('/api/versions/audit'),{timeout:220000});await page.getByRole('button',{name:'检查证据变化',exact:true}).click();
 const response=await responsePromise;assert.equal(response.status(),200);const actual=await response.json();report.real_audit=actual;assert.ok(actual.results.length);await page.getByRole('button',{name:'导出复核报告'}).waitFor();
 const reportDownload=page.waitForEvent('download');await page.getByRole('button',{name:'导出复核报告'}).click();await(await reportDownload).saveAs(folder+'/real-version-review.json');check('真实本地模型复核现有两版论文并导出报告');
 await page.screenshot({path:folder+'/real-audit.png',fullPage:true});
 // Controlled UI replay, not a quality benchmark, and no user records are written.
 const rows=Array.from({length:13},(_,i)=>({...actual.results[0],note:{...actual.results[0].note,id:1000+i,note:'界面回放样例 '+i},semantic_review:i<12?{status:'model_assessment',decision:'same_claim',reason:'UI replay'}:{status:'not_checked',reason:'UI replay'}}));
 let calls=0;await page.route('**/api/versions/audit',route=>{const body=route.request().postDataJSON();calls++;if(calls===2)assert.deepEqual(body.note_ids,[1012]);return route.fulfill({json:{results:calls===1?rows:rows.map((r,i)=>({...r,semantic_review:i===12?{status:'model_assessment',decision:'unclear',reason:'UI replay'}:{status:'not_checked',reason:'UI replay'}}))}});});
 await page.getByRole('button',{name:'检查证据变化',exact:true}).click();await page.getByRole('button',{name:'继续复核未检查项'}).click();await page.getByRole('button',{name:'继续复核未检查项'}).waitFor({state:'detached'});assert.ok((await page.locator('.audit-coverage').innerText()).includes('12'));assert.equal(await page.locator('.audit-card').count(),13);check('受控界面回放：第二批复核保留首批 12 条结果，合计显示 13 条');
 await page.setViewportSize({width:390,height:844});const dimensions=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth}));report.mobile=dimensions;assert.ok(dimensions.scroll<=dimensions.width+1);await page.screenshot({path:folder+'/mobile-audit-replay.png',fullPage:true});check('390px 复核页无横向溢出');
 await page.setViewportSize({width:1440,height:1000});
 await page.getByRole('button',{name:/^证据笔记/}).click();await page.getByRole('button',{name:'编辑观察',exact:true}).first().click();
 const editor=page.getByLabel('编辑笔记内容');await editor.fill('界面回放：冲突后保留的草稿');
 let patched=false;await page.route('**/api/notes/*',r=>{assert.equal(r.request().method(),'PATCH');assert.equal(typeof r.request().postDataJSON().expected_note,'string');patched=true;return r.fulfill({status:409,json:{detail:'这条笔记已在其他页面更新。你的草稿仍保留。'}});});
 await page.getByRole('button',{name:'保存修改',exact:true}).click();await page.getByText('这条笔记已在其他页面更新。你的草稿仍保留。',{exact:true}).waitFor();assert.ok(patched);assert.equal(await editor.inputValue(),'界面回放：冲突后保留的草稿');await page.getByRole('button',{name:'查看最新笔记，保留草稿'}).click();assert.equal(await editor.inputValue(),'界面回放：冲突后保留的草稿');check('受控 409 界面回放：旧笔记编辑带比较基准，冲突和刷新后草稿仍保留');
 assert.deepEqual(report.errors,[]);
}catch(e){report.failure=String(e);process.exitCode=1;await page.screenshot({path:folder+'/failure.png',fullPage:true});}finally{await writeFile(folder+'/browser-report.json',JSON.stringify(report,null,2));console.log(JSON.stringify({checks:report.checks,errors:report.errors,failure:report.failure,mobile:report.mobile}));await browser.close();}
