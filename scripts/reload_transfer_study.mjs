import assert from 'node:assert/strict';
import {readFileSync,writeFileSync} from 'node:fs';
import {ownedProcess,health,delay} from './runtime.mjs';
const folder=process.env.SCHOLARTRACE_CHECK_FOLDER || 'artifacts/transfer-comparison-20261020';
const record=name=>JSON.parse(readFileSync(`artifacts/runtime/${name}.process.json`,'utf8'));
const jobs=JSON.parse(readFileSync(`${folder}/jobs-before-reload.json`,'utf8'));
assert.ok(jobs.length&&jobs.every(j=>j.active.length===0));
const active=await(await fetch('http://127.0.0.1:8765/api/jobs')).json();
assert.ok(active.every(j=>!['queued','running'].includes(j.state)));
const before={server:record('server'),model:record('model'),health:await health()};
assert.ok(ownedProcess('server',true),'Only verified project server can be stopped');
let after;
for(let i=0;i<60;i++){
 await delay(500);
 const current=await health();
 if(current?.model_available&&record('server').pid!==before.server.pid){after={server:record('server'),model:record('model'),health:current};break;}
}
assert.ok(after,'Supervisor should restart healthy updated backend');
assert.deepEqual(after.model,before.model);
writeFileSync(`${folder}/main-reload.json`,JSON.stringify({before,after,model_preserved:true},null,2));
console.log(JSON.stringify(after,null,2));
