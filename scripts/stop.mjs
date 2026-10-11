import { execFileSync } from 'node:child_process';
import { readFileSync, existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
for (const [name, executable] of [['server', '.venv/Scripts/python.exe'], ['model', 'tools/llama/llama-server.exe']]) {
  const pidFile = path.join(root, `artifacts/runtime/${name}.pid`);
  if (!existsSync(pidFile)) continue;
  const id = Number(readFileSync(pidFile, 'utf8').trim());
  if (!Number.isInteger(id) || id <= 0) throw new Error(`Invalid ${name} process id`);
  const expected = path.join(root, executable).replaceAll("'", "''");
  const command = `$ownedTask = Get-Process -Id ${id} -ErrorAction SilentlyContinue; if ($ownedTask) { if ($ownedTask.Path -ne '${expected}') { throw 'Process path does not match this project; refusing to stop it' }; & taskkill.exe /PID ${id} /T /F }`;
  execFileSync('powershell.exe', ['-NoProfile', '-Command', command], { windowsHide: true, stdio: 'inherit' });
}
console.log('ScholarTrace services stopped.');
