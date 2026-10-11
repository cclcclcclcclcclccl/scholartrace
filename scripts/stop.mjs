import { writeFileSync, mkdirSync } from 'node:fs';
import path from 'node:path';
import { logs, delay, ownedProcess } from './runtime.mjs';
mkdirSync(logs, { recursive: true });
writeFileSync(path.join(logs, 'stop.request'), 'stop');
for (let i = 0; i < 15 && ownedProcess('supervisor'); i++) await delay(500);
if (ownedProcess('supervisor')) ownedProcess('supervisor', true);
for (const name of ['server', 'model']) ownedProcess(name, true);
console.log('ScholarTrace services stopped.');
