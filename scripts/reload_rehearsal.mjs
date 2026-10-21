import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { ownedProcess, health, delay } from './runtime.mjs';
const record = name => JSON.parse(readFileSync(`artifacts/runtime/${name}.process.json`,'utf8'));
const before = {server:record('server'), model:record('model'), health:await health()};
const jobs=JSON.parse(readFileSync('artifacts/rehearsal-20261020/jobs-before-reload.json','utf8'));
assert.ok(jobs.length && jobs.every(item=>item.active.length===0));
if (before.health) {
  const active=await (await fetch('http://127.0.0.1:8765/api/jobs')).json();
  assert.ok(active.every(j=>!['queued','running'].includes(j.state)));
  assert.ok(ownedProcess('server',true),'Server identity must match before restart');
}
execFileSync(process.execPath,['scripts/start.mjs'],{windowsHide:true,stdio:'pipe'});
let ready=null;
for(let i=0;i<60;i++) {
  try {
    const r=await fetch('http://127.0.0.1:8765/api/rehearsal');
    if(r.ok && (await health())?.model_available){ready=await r.json();break;}
  } catch {}
  await delay(500);
}
assert.ok(ready,'Updated rehearsal API must be available');
const after={server:record('server'),model:record('model'),health:await health()};
const result={before,after,rehearsal_api:200,main_session_count:ready.total};
writeFileSync('artifacts/rehearsal-20261020/main-reload.json',JSON.stringify(result,null,2));
console.log(JSON.stringify(result,null,2));
