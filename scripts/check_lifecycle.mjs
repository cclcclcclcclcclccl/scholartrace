import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { writeFileSync } from 'node:fs';
import { root, health, delay, portOpen } from './runtime.mjs';
const run = script => execFileSync(process.execPath, [script], { cwd: root, windowsHide: true, stdio: 'pipe' });
const before = await (await fetch('http://127.0.0.1:8765/api/documents')).json();
try {
  run('scripts/stop.mjs');
  assert.equal(await portOpen(8765), false, 'Stop must close web service');
  assert.equal(await portOpen(8081), false, 'Stop must close local model');
  run('scripts/stop.mjs');
} finally { run('scripts/start.mjs'); }
let status;
for (let i = 0; i < 45; i++) {
  status = await health();
  if (status?.model_available) break;
  await delay(1000);
}
assert.ok(status?.model_available, 'Local model failed to become ready');
assert.deepEqual(await (await fetch('http://127.0.0.1:8765/api/documents')).json(), before);
const result = { passed: true, stop_closed_both_ports: true, repeated_stop_safe: true, restart_restored_web_and_model: true, documents_preserved: before.length };
writeFileSync('artifacts/inspection/lifecycle-check.json', JSON.stringify(result, null, 2));
console.log(JSON.stringify(result, null, 2));
