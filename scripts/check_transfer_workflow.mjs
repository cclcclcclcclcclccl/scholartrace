import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {readFile,writeFile} from 'node:fs/promises';
const {chromium}=createRequire(import.meta.url)('C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const folder=process.env.SCHOLARTRACE_CHECK_FOLDER || 'artifacts/transfer-comparison-20261020/workflow',base='http://127.0.0.1:8767';
const fixture=JSON.parse(await readFile(`${folder}/fixture.json`,'utf8'));
const attempt=process.argv[2] || 'first';
const report={notice:'开发者自动化走查，操作耗时包含程序等待；不是真人效率、满意度或用户实验。项目预置；其他记录经页面操作。',steps:[],errors:[],complete:false};
const start=performance.now();
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:true});
page.setDefaultTimeout(20000);
page.on('pageerror',e=>report.errors.push(String(e)));
async function action(name,fn){const t=performance.now();await fn();report.steps.push({name,seconds:+((performance.now()-t)/1000).toFixed(3)});}
try{
  await page.goto(base);
  await page.getByRole('dialog').waitFor();
  await action('关闭首次使用教程',()=>page.keyboard.press('Escape'));
  const sources=[
    {paper:fixture.papers[0],query:'Layer normalization batch size 1 pure online regime',block:'d8678cd1dab39c165ca66171',note:`真实论文走查 ${attempt}：LN可用于单样本在线学习，统计量按样本计算。`},
    {paper:fixture.papers[1],query:'Post-LN Pre-LN expected gradients at initialization warm-up',block:'966ff2ae0bf0e6614b4f4c32',note:`真实论文走查 ${attempt}：Pre-LN移除warm-up的依据须保留初始化与实验范围。`},
  ];
  const noteIds=[];
  for(const [index,item] of sources.entries()){
    await page.setViewportSize({width:390,height:844});
    await action(`选择论文 ${index+1}`,()=>page.getByLabel('选择阅读文献').selectOption(item.paper.id));
    await page.setViewportSize({width:1440,height:1000});
    if(index===0){
      for(const n of [7,6,9]){
        await action(`清空页码并输入 ${n}`,async()=>{await page.getByRole('spinbutton').fill('');await page.getByRole('spinbutton').fill(String(n));await page.getByRole('spinbutton').press('Enter');});
        assert.equal(await page.getByRole('spinbutton').getAttribute('aria-valuenow'),String(n));
      }
    }
    await action(`输入论文 ${index+1} 的检索问题`,()=>page.getByLabel('研究问题',{exact:true}).fill(item.query));
    const resultPromise=page.waitForResponse(r=>r.url().endsWith('/api/ask')&&r.request().method()==='POST',{timeout:360000});
    await action('按回车发送问题',()=>page.getByLabel('研究问题',{exact:true}).press('Enter'));
    let result;
    await action('等待真实本地问答及原文卡片',async()=>{result=await(await resultPromise).json();await page.locator('.evidence-card').first().waitFor();});
    const sourceIndex=result.evidence.findIndex(b=>b.id===item.block);
    assert.ok(sourceIndex>=0,'Target real source must be retrieved');
    const card=page.locator('.evidence-card').nth(sourceIndex);
    await action('定位对应PDF原文',()=>card.locator('.evidence-content').click());
    assert.equal(await page.getByRole('spinbutton').getAttribute('aria-valuenow'),String(result.evidence[sourceIndex].page));
    await action('存为证据笔记',()=>card.getByRole('button',{name:'存为笔记',exact:true}).click());
    await action('填写研究观察',()=>card.getByLabel('证据笔记内容').fill(item.note));
    const save=page.waitForResponse(r=>r.url().endsWith('/api/notes')&&r.request().method()==='POST');
    await action('保存原文证据',()=>card.getByRole('button',{name:'保存证据',exact:true}).click());
    const saved=await(await save).json();noteIds.push(saved.id);
    assert.equal(saved.block_id,item.block);
  }
  await action('进入证据笔记',()=>page.getByRole('button',{name:/^证据笔记/}).click());
  const panel=page.getByRole('region',{name:'证据边界对照表',exact:true});
  await action('打开边界对照',()=>panel.getByRole('button',{name:'开始边界对照'}).click());
  await action('填写对照标题',()=>panel.getByLabel('对照表标题').fill(`真实归一化条件对照 ${attempt}`));
  for(const item of sources)await action('勾选真实来源笔记',()=>panel.getByLabel(`对照证据：${item.note}`,{exact:true}).check());
  const created=page.waitForResponse(r=>r.url().endsWith('/api/boundaries')&&r.request().method()==='POST');
  await action('创建对照表',()=>panel.getByRole('button',{name:'创建边界对照 · 2 条证据'}).click());
  const comparison=await(await created).json();
  await action('关联走查项目',()=>panel.getByLabel('补查待办归属项目').selectOption(fixture.project.id));
  await action('从空白实验条件格创建待办',()=>panel.getByRole('button',{name:`加入补查：实验条件：${sources[0].paper.title}`,exact:true}).click());
  const tasks=page.getByRole('region',{name:'研究补查待办',exact:true});
  const task=tasks.locator('.research-task').filter({hasText:`补查实验条件 · ${sources[0].paper.title}`}).first();
  await action('开始补查',()=>task.getByRole('button',{name:'开始补查',exact:true}).click());
  await action('记录补查依据',()=>task.getByRole('button',{name:'记录依据并回填',exact:true}).click());
  const editor=tasks.getByRole('region',{name:'补查待办编辑'});
  await action('选择本篇原文笔记',()=>editor.getByLabel('补查来源笔记').selectOption(String(noteIds[0])));
  const quote='layer normaliztion does not impose any constraint on the size of a mini-batch and it can be used in\nthe pure online regime with batch size 1.';
  const outcome='LayerNorm 不限制 mini-batch 大小；论文明确说明可在 batch size 1 的纯在线场景使用。不能据此推断任意任务都提升精度。';
  await action('填写有范围的研究整理',()=>editor.getByLabel('补查处理说明').fill(outcome));
  await action('填写对应的原文摘录',()=>editor.getByLabel('补查对应摘录').fill(quote));
  await action('保存并回填对照',()=>editor.getByRole('button',{name:'保存依据并回填',exact:true}).click());
  await task.locator('.task-state').getByText('已回填',{exact:true}).waitFor();
  await action('返回对照表检查回填',()=>task.getByRole('button',{name:'返回对应对照表'}).click());
  await panel.locator('tbody').getByText(outcome,{exact:true}).waitFor();
  await page.screenshot({path:`${folder}/${attempt}-desktop.png`,fullPage:true});
  const exported=await(await page.request.get(`${base}/api/projects/${fixture.project.id}/export`)).json();
  const exportedTask=exported.research_tasks.find(t=>t.comparison_id===comparison.id);
  assert.equal(exportedTask.state,'done');assert.equal(exportedTask.evidence.cell.value,outcome);
  assert.ok(exportedTask.events.some(e=>e.state==='done'&&e.evidence.cell.quote===quote));
  await writeFile(`${folder}/${attempt}-project-export.json`,JSON.stringify(exported,null,2));
  const bundle=await page.request.get(`${base}/api/projects/${fixture.project.id}/bundle`);assert.equal(bundle.status(),200);
  await writeFile(`${folder}/${attempt}-project-export.zip`,await bundle.body());
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.screenshot({path:`${folder}/${attempt}-mobile.png`,fullPage:true});
  report.complete=true;report.export_verified=true;report.note_ids=noteIds;report.comparison_id=comparison.id;
}catch(error){report.error=String(error);await page.screenshot({path:`${folder}/${attempt}-failure.png`,fullPage:true});throw error;}
finally{report.total_seconds=+((performance.now()-start)/1000).toFixed(3);await writeFile(`${folder}/${attempt}-browser.json`,JSON.stringify(report,null,2));await browser.close();console.log(JSON.stringify(report,null,2));}
