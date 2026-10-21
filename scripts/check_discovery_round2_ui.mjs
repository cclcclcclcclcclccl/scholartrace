import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {writeFile} from 'node:fs/promises';
const {chromium}=createRequire(import.meta.url)('C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const folder='artifacts/discovery-round2';
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
page.setDefaultTimeout(180000);
const report={checks:[],errors:[]};page.on('pageerror',e=>report.errors.push(String(e)));
async function search(query){await page.getByLabel('论文检索词',{exact:true}).fill(query);const done=page.waitForResponse(r=>r.url().endsWith('/api/discover/search')&&r.request().method()==='POST');await page.getByRole('button',{name:'搜索论文',exact:true}).click();const r=await done;const body=await r.json();assert.equal(r.status(),200,JSON.stringify(body));return body;}
try {
 await page.goto('http://127.0.0.1:8765/');await page.getByRole('dialog').waitFor();await page.keyboard.press('Escape');
 await page.getByRole('button',{name:'论文发现',exact:true}).click();
 await page.getByLabel('检索方式').selectOption('identifier');
 const doi=await search('https://doi.org/10.1038/nature14539');assert.equal(doi[0].doi,'10.1038/nature14539');assert.equal(doi[0].title,'Deep learning');report.checks.push('真实 DOI 链接直查 Deep learning');report.doi=doi;
 const arxiv=await search('https://arxiv.org/abs/1706.03762v7');assert.equal(arxiv[0].arxiv_id,'1706.03762v7');assert.ok(arxiv[0].library_matches.some(p=>p.version===1&&p.different_version));report.checks.push('真实 arXiv 版本直查，识别库内 v1/v7');report.arxiv=arxiv;
 await page.screenshot({path:`${folder}/identifier-desktop.png`,fullPage:true});
 const localId=arxiv[0].library_matches.find(p=>p.version===7).id;
 await page.locator('.discovery-seed summary').click();
 await page.getByLabel('关联种子论文').selectOption(localId);
 let done=page.waitForResponse(r=>r.url().endsWith('/api/discover/related'));
 await page.getByRole('button',{name:'查找相关文章',exact:true}).click();
 let related=await (await done).json();assert.ok(related.local.length);assert.ok(related.local.every(p=>!p.title.toLowerCase().includes('attention is all you need')));report.local=related;report.checks.push('种子关联排除自身与同篇其他版本，展示共同词');
 await page.getByLabel('同时查找在线论文').check();done=page.waitForResponse(r=>r.url().endsWith('/api/discover/related'));
 await page.getByRole('button',{name:'查找相关文章',exact:true}).click();related=await (await done).json();report.online=related;assert.ok(related.local.length);assert.ok(related.papers.length||related.warnings.length);report.checks.push(related.papers.length?'真实 Crossref 关联扩展返回论文':'在线扩展失败提示且本地结果保留');
 await page.screenshot({path:`${folder}/related-desktop.png`,fullPage:true});
 await page.getByText('功能与用法',{exact:true}).click();assert.ok((await page.locator('body').innerText()).includes('系统不自动替换旧证据'));report.checks.push('模块教程包含精确查找、关联推荐与版本复核流程');
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:`${folder}/mobile.png`,fullPage:true});
 report.mobile=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth}));assert.ok(report.mobile.scroll<=report.mobile.width+1,JSON.stringify(report.mobile));
 await page.getByRole('button',{name:'打开阅读',exact:true}).first().click();await page.locator('.paper-stage').waitFor();report.checks.push('关联论文直接进入阅读台');assert.deepEqual(report.errors,[]);
} catch(e) {report.failure=String(e);await page.screenshot({path:`${folder}/failure.png`,fullPage:true});process.exitCode=1;} finally {await writeFile(`${folder}/browser-report.json`,JSON.stringify(report,null,2));console.log(JSON.stringify({checks:report.checks,errors:report.errors,failure:report.failure,mobile:report.mobile},null,2));await browser.close();}
