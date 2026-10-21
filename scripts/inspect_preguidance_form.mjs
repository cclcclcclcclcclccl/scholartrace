import {createRequire} from 'node:module';
import {mkdir,writeFile} from 'node:fs/promises';
const {chromium}=createRequire(import.meta.url)('C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const folder='artifacts/preguidance-20261021';
await mkdir(folder,{recursive:true});
const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
const report={url:'https://f.kdocs.cn/ksform/w/write/n2ch15Dh#routePromt',read_only:true,used_personal_session:false};
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 await page.goto(report.url,{waitUntil:'domcontentloaded',timeout:45000});
 await page.getByText('作品介绍文档',{exact:false}).first().waitFor({timeout:20000});
 report.title=await page.title();report.text=await page.locator('body').innerText();
 report.inputs=await page.locator('input').evaluateAll(es=>es.map(e=>({type:e.type,accept:e.accept,placeholder:e.placeholder})));
 await page.screenshot({path:folder+'/form-live.png',fullPage:true});
 report.loaded=true;
}catch(e){report.loaded=false;report.failure=String(e);}
finally{await browser.close();await writeFile(folder+'/form-live.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));}
