import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { chromium } = require('C:/Users/34711/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const browser = await chromium.launch({ executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe', headless:true });
const page = await browser.newPage({viewport:{width:1512,height:1100}});
page.on('console', message => { if (message.type() !== 'debug') console.log(message.type(), message.text()); });
page.on('pageerror', error => console.log('PAGE ERROR',String(error)));
page.on('requestfailed', request => console.log('FAILED',request.url(),request.failure()));
try {
  await page.goto('http://127.0.0.1:8765',{waitUntil:'domcontentloaded',timeout:15000});
  await page.waitForTimeout(10000);
  console.log((await page.locator('body').innerText()).slice(0,4000));
  await page.screenshot({path:'artifacts/browser/debug.png',fullPage:true});
} finally {await browser.close();}
