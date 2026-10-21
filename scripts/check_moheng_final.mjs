import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {writeFile,readFile} from 'node:fs/promises';
const {chromium}=createRequire(import.meta.url)('C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const folder='artifacts/moheng-final-20261021',base='http://127.0.0.1:8766';
const b=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
const p=await b.newPage({viewport:{width:1440,height:1000}});p.setDefaultTimeout(20000);
const report={checks:[],errors:[],complete:false,scope:'Isolated database; genuine backend, no mocked responses'};
p.on('pageerror',e=>report.errors.push(String(e)));
try {
 await p.goto(base);await p.getByRole('dialog').waitFor();assert.match(await p.title(),/墨衡/);
 await p.keyboard.press('Control+k');assert.equal(await p.locator('dialog[open]').count(),1);report.checks.push('快捷键不覆盖教程弹窗');
 await p.keyboard.press('Escape');await p.getByRole('button',{name:/快捷查找/}).click();
 const q=p.getByRole('combobox',{name:'搜索功能或库内论文'});await q.fill('画图');assert.equal(await p.locator('.quick-dialog').getByRole('option').count(),1);
 await q.evaluate(el=>el.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,isComposing:true})));assert.equal(await p.locator('dialog[open]').count(),1);
 await q.press('Enter');await p.getByLabel('研究目标',{exact:true}).waitFor();report.checks.push('中文输入法确认不误跳转，Enter打开正确工具');
 await p.keyboard.press('Control+k');await q.fill('1706.03762v1.pdf');assert.ok(await p.locator('.quick-dialog').getByRole('option').count());
 await q.press('Enter');await p.getByLabel('研究问题',{exact:true}).waitFor();report.checks.push('快捷查找按文件名直接打开库内论文');
 const jump=p.getByLabel('当前页码');await jump.fill('');assert.equal(await jump.inputValue(),'');await jump.fill('7');await jump.press('Enter');await p.waitForFunction(()=>document.querySelector('.paper-stage')?.getAttribute('aria-busy')==='false');assert.equal(await jump.inputValue(),'7');report.checks.push('页码可删空、输入7并定位');
 await p.getByLabel('研究问题',{exact:true}).fill('暂不发送的验收问题');await p.getByLabel('研究问题',{exact:true}).press('Shift+Enter');assert.match(await p.getByLabel('研究问题',{exact:true}).inputValue(),/\n/);
 await p.getByRole('button',{name:/快捷查找/}).click();await q.fill('找不到的文章x9381');await p.getByText('没有匹配的功能或库内论文',{exact:true}).waitFor();await p.getByRole('button',{name:'前往论文发现'}).click();await p.getByRole('heading',{name:/发现/}).first().waitFor();report.checks.push('空搜索明确区分库内查找与联网发现');
 await p.getByRole('button',{name:/快捷查找/}).click();await q.fill('版本');await q.press('ArrowDown');const active=await q.getAttribute('aria-activedescendant');assert.ok(active&&await p.locator('#'+active).count());await p.screenshot({path:folder+'/quick-search-desktop.png'});await q.press('Escape');assert.ok(await p.getByRole('button',{name:/快捷查找/}).evaluate(el=>el===document.activeElement));report.checks.push('方向键、选中项和Esc焦点恢复');
 // Real partial batch: first file fails, second is a valid duplicate PDF.
 const data=await readFile('data/competition/pdf/1706.03762v1.pdf');
 const finished=p.waitForResponse(r=>r.url().endsWith('/api/documents')&&r.request().method()==='POST'&&r.status()===200);
 await p.locator('input[type=file][accept="application/pdf,.pdf"]').setInputFiles([{name:'invalid-final.pdf',mimeType:'application/pdf',buffer:Buffer.from('not a pdf')},{name:'1706.03762v1.pdf',mimeType:'application/pdf',buffer:data}]);
 await finished;await p.getByRole('alert').filter({hasText:'invalid-final.pdf'}).waitFor();await p.getByRole('status').filter({hasText:'1 份文件已导入或复用已有文献，1 份失败'}).waitFor();report.checks.push('真实批量导入失败后继续，成功项刷新且逐文件提示');
 await p.getByRole('button',{name:'关闭错误',exact:true}).click();
 await p.setViewportSize({width:390,height:844});await p.getByRole('button',{name:/快捷查找/}).click();await q.fill('翻译');await p.screenshot({path:folder+'/quick-search-mobile.png'});
 assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.ok(await p.locator('dialog[open]').evaluate(el=>el.scrollWidth<=el.clientWidth+1));report.checks.push('390px快捷入口与弹窗无横向溢出');
 await q.press('Escape');
 for(const label of ['文献管理','论文发现','研究项目','科研工作室','版本复核','证据笔记']){
  await p.getByRole('button',{name:label,exact:true}).first().click();assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),label);report.checks.push('手机布局：'+label);
 }
 assert.equal((await(await p.request.get(base+'/api/health')).json()).model_available,true);
 assert.deepEqual(report.errors,[]);report.complete=true;
} catch(e) {report.failure=String(e);await p.screenshot({path:folder+'/browser-failure.png',fullPage:true});throw e;}
finally{await writeFile(folder+'/browser-final.json',JSON.stringify(report,null,2));await b.close();console.log(JSON.stringify(report,null,2));}
