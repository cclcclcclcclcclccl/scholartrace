import { spawn } from 'node:child_process';
import { existsSync, openSync, closeSync, mkdirSync, writeFileSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { root, logs, python, delay, portOpen, ownedProcess } from './runtime.mjs';

mkdirSync(logs, { recursive: true });
const selectionPath = path.join(root, 'config/model-runtime.json');
const selection = existsSync(selectionPath) ? JSON.parse(readFileSync(selectionPath, 'utf8')) : {};
const modelFile = selection.model_file || 'models/Qwen3-4B-Q4_K_M.gguf';
if (!['models/Qwen3-4B-Q4_K_M.gguf', 'models/Qwen3-4B-Instruct-2507-Q4_K_M.gguf'].includes(modelFile)) throw Error('Unsupported local model selection');
if (existsSync(path.join(root, '.env'))) process.loadEnvFile(path.join(root, '.env'));
writeFileSync(path.join(logs, 'supervisor.process.json'), JSON.stringify({ pid: process.pid, executable: process.execPath, startedAt: Date.now() }));
const services = [
  { name: 'server', port: 8765, executable: python, args: ['-X', 'utf8', '-m', 'uvicorn', 'backend.app:app', '--host', '127.0.0.1', '--port', '8765'] },
  { name: 'model', port: 8081, executable: path.join(root, 'tools/llama/llama-server.exe'), args: ['-m', path.join(root, modelFile), '--host', '127.0.0.1', '--port', '8081', '-ngl', '99', '-c', '8192', '-b', '512', '-ub', '128', '-np', '1', '-t', '8', '--jinja'] },
].map(item => ({ ...item, child: null, failures: 0, nextAttempt: 0, started: 0 }));
const log = message => console.log(new Date().toISOString() + ' ' + message);
let stopping = false;
process.on('SIGTERM', () => { stopping = true; });
process.on('SIGINT', () => { stopping = true; });
log('Independent supervisor started');
while (!stopping && !existsSync(path.join(logs, 'stop.request'))) {
  for (const service of services) {
    // Explicit local maintenance marker releases only the model, keeping the web service alive.
    if (service.name === 'model' && existsSync(path.join(logs, 'model.pause'))) {
      if (service.child) ownedProcess('model', true);
      continue;
    }
    if (service.child || Date.now() < service.nextAttempt || !existsSync(service.executable)) continue;
    if (service.name === 'model' && !existsSync(service.args[1])) continue;
    // Loading models return HTTP 503 but already own their listening port.
    if (await portOpen(service.port)) continue;
    const out = openSync(path.join(logs, service.name + '.log'), 'a');
    const err = openSync(path.join(logs, service.name + '.error.log'), 'a');
    const startedAt = Date.now();
    const child = spawn(service.executable, service.args, { cwd: root, windowsHide: true, stdio: ['ignore', out, err] });
    closeSync(out); closeSync(err);
    service.child = child;
    service.started = startedAt;
    if (child.pid) {
      writeFileSync(path.join(logs, service.name + '.pid'), String(child.pid));
      writeFileSync(path.join(logs, service.name + '.process.json'), JSON.stringify({ pid: child.pid, executable: service.executable, startedAt }));
    }
    log(service.name + ' starting, pid=' + child.pid);
    child.once('error', error => log(service.name + ': ' + error.message));
    child.once('close', code => {
      service.child = null;
      service.failures = Date.now() - service.started > 60000 ? 1 : service.failures + 1;
      const backoff = Math.min(30000, 1000 * 2 ** Math.min(service.failures, 5));
      service.nextAttempt = Date.now() + backoff;
      log(service.name + ' exited (' + code + '); retry in ' + backoff + 'ms');
    });
  }
  writeFileSync(path.join(logs, 'supervisor-status.json'), JSON.stringify({ pid: process.pid, heartbeat: new Date().toISOString(), services: services.map(s => ({ name: s.name, pid: s.child?.pid ?? null, retries: s.failures })) }));
  await delay(1000);
}
for (const service of services) ownedProcess(service.name, true);
log('Supervisor stopped');
