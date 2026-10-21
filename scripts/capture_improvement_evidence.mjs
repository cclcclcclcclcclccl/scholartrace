import { createRequire } from 'node:module';
const {chromium}=createRequire(import.meta.url)('C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const b=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
const p=await b.newPage({viewport:{width:1440,height:1000}});
try {
 await p.goto('http://127.0.0.1:8766');await p.getByRole('dialog').waitFor();await p.keyboard.press('Escape');
 await p.getByText('更多工具与成果',{exact:true}).click();
 await p.getByRole('button',{name:'任务与成果',exact:true}).click();
 await p.getByRole('button').filter({hasText:'CLIP 预训练数据的规模和组成是什么？请区分图文对数量与 ImageNet 训练图片数量。'}).first().click();
 const c=p.locator('.artifact-result .answer-coverage');await c.waitFor();await c.screenshot({path:'artifacts/improvement-v8/partial-desktop.png'});
 await p.goto(new URL('../evaluation/reliability/report.html',import.meta.url).href);await p.screenshot({path:'artifacts/improvement-v8/reliability-dashboard.png'});
 console.log('Saved artifact coverage and complete reliability dashboard rendered');
}finally{await b.close();}
