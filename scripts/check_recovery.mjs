// Deliberately stop only the verified project server; the supervisor must recover it.
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { logs, root, health, delay, ownedProcess } from './runtime.mjs';

assert.ok(await health(), 'Start the project before checking recovery');
const beforeDocs = await (await fetch('http://127.0.0.1:8765/api/documents')).json();
const beforeNotes = await (await fetch('http://127.0.0.1:8765/api/notes')).json();
const original = JSON.parse(readFileSync(path.join(logs, 'server.process.json')));
const supervisor = JSON.parse(readFileSync(path.join(logs, 'supervisor.process.json')));
assert.ok(ownedProcess('server', true), 'Refuse to stop a process not owned by this project');
const start = Date.now();
let ready = false;
for (let i = 0; i < 60; i++) {
  await delay(500);
  const record = JSON.parse(readFileSync(path.join(logs, 'server.process.json')));
  if (record.pid !== original.pid && await health()) { ready = true; break; }
}
assert.ok(ready, 'Web service failed to recover within 30s');
const recoveredMs = Date.now() - start;
execFileSync(process.execPath, ['scripts/start.mjs'], { cwd: root, windowsHide: true, stdio: 'pipe' });
const afterSupervisor = JSON.parse(readFileSync(path.join(logs, 'supervisor.process.json')));
assert.equal(afterSupervisor.pid, supervisor.pid, 'Repeated start must reuse the supervisor');
assert.deepEqual(await (await fetch('http://127.0.0.1:8765/api/documents')).json(), beforeDocs);
assert.deepEqual(await (await fetch('http://127.0.0.1:8765/api/notes')).json(), beforeNotes);
const result = { passed: true, recovered_ms: recoveredMs, supervisor_pid: supervisor.pid, documents_preserved: beforeDocs.length, notes_preserved: beforeNotes.length, repeated_start_reused_supervisor: true };
writeFileSync('artifacts/inspection/recovery-check.json', JSON.stringify(result, null, 2));
console.log(JSON.stringify(result, null, 2));
