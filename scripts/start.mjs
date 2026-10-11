import { spawn } from 'node:child_process';
import { openSync, existsSync, mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const logs = path.join(root, 'artifacts/runtime');
mkdirSync(logs, { recursive: true });
const python = path.join(root, '.venv/Scripts/python.exe');
if (!existsSync(python)) throw new Error('Python environment missing. Follow README setup instructions.');
if (!existsSync(path.join(root, 'frontend/dist/index.html'))) throw new Error('Frontend build missing. Run npm run build in frontend.');

async function responds(url) {
  try { const response = await fetch(url, { signal: AbortSignal.timeout(1200) }); return response.ok; } catch { return false; }
}
function background(command, args, name) {
  const out = openSync(path.join(logs, `${name}.log`), 'a');
  const err = openSync(path.join(logs, `${name}.error.log`), 'a');
  const process = spawn(command, args, { cwd: root, detached: true, windowsHide: true, stdio: ['ignore', out, err] });
  process.on('error', error => console.error(`${name}: ${error.message}`));
  process.unref();
  if (process.pid) writeFileSync(path.join(logs, `${name}.pid`), String(process.pid));
}

const runtime = path.join(root, 'tools/llama/llama-server.exe');
const model = path.join(root, 'models/Qwen3-4B-Q4_K_M.gguf');
if (existsSync(runtime) && existsSync(model) && !(await responds('http://127.0.0.1:8081/health'))) {
  background(runtime, ['-m', model, '--host', '127.0.0.1', '--port', '8081', '-ngl', '99', '-c', '8192', '-np', '1', '-t', '8', '--jinja'], 'model');
  console.log('Starting local Qwen model. Initial loading may take a little time.');
}
if (!(await responds('http://127.0.0.1:8765/api/health'))) {
  background(python, ['-X', 'utf8', '-m', 'uvicorn', 'backend.app:app', '--host', '127.0.0.1', '--port', '8765'], 'server');
}
for (let attempt = 0; attempt < 25; attempt++) {
  if (await responds('http://127.0.0.1:8765/api/health')) {
    console.log('ScholarTrace: http://127.0.0.1:8765');
    if (process.argv.includes('--open')) spawn('explorer.exe', ['http://127.0.0.1:8765'], { windowsHide: true, detached: true, stdio: 'ignore' }).unref();
    process.exit(0);
  }
  await new Promise(resolve => setTimeout(resolve, 500));
}
throw new Error('Server did not become ready. Check artifacts/runtime/server.error.log');
