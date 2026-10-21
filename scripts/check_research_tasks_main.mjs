import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {writeFile} from 'node:fs/promises';
const {chromium}=createRequire(import.meta.url)('C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const base='http://127.0.0.1:8765',folder='artifacts/research-tasks-20261020';
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
const report={errors:[]};
try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  page.on('pageerror',e=>report.errors.push(String(e)));
  await page.goto(base);await page.getByRole('dialog').waitFor();await page.keyboard.press('Escape');
  await page.getByRole('button',{name:/^证据笔记/}).click();
  const panel=page.getByRole('region',{name:'证据边界对照表',exact:true});
  await panel.getByRole('button',{name:'开始边界对照'}).click();
  await panel.getByText('已保存的对照表（0）',{exact:true}).click();
  await panel.getByLabel('查看已归档对照表').check();
  const archive=await(await page.request.get(base+'/api/boundaries?archived=true')).json();
  assert.equal(archive.total,0);
  const projects=await(await page.request.get(base+'/api/projects')).json();
  assert.ok(projects.length,'An original project should exist for read-only checks');
  const project=projects.find(p=>!p.archived)||projects[0];
  await page.goto(`${base}/#project=${project.id}`);await page.reload();
  await page.getByRole('button',{name:'研究补查待办',exact:true}).click();
  const tasks=page.getByRole('region',{name:'研究补查待办',exact:true});
  await tasks.getByText('还没有补查待办。在证据边界对照表中，从“待补查”单元格创建。',{exact:true}).waitFor();
  await tasks.getByText('补查待办怎么用？',{exact:true}).click();
  await tasks.screenshot({path:`${folder}/main-desktop.png`});
  report.task_count=(await(await page.request.get(`${base}/api/research-tasks?project_id=${project.id}`)).json()).total;
  assert.equal(report.task_count,0);
  await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await tasks.screenshot({path:`${folder}/main-mobile.png`});
  assert.deepEqual(report.errors,[]);report.loaded=true;report.mobile_fits=true;
}catch(e){report.failure=String(e.stack||e);process.exitCode=1;}
finally{await writeFile(`${folder}/main-browser.json`,JSON.stringify(report,null,2));await browser.close();}
console.log(JSON.stringify(report,null,2));
