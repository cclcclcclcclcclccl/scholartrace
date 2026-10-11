import { spawn, execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, unlinkSync, openSync, closeSync, statSync } from 'node:fs';
import path from 'node:path';
import { root, logs, python, health, delay, ownedProcess } from './runtime.mjs';

mkdirSync(logs, { recursive: true });
if (!existsSync(python)) throw Error('Python environment missing. Follow README setup instructions.');
if (!existsSync(path.join(root, 'frontend/dist/index.html'))) throw Error('Frontend build missing. Run npm run build in frontend.');
const lock = path.join(logs, 'start.lock');
if (existsSync(lock) && Date.now() - statSync(lock).mtimeMs > 180000) unlinkSync(lock);
let handle;
try { handle = openSync(lock, 'wx'); } catch { throw Error('Another launch is in progress. Wait for it to finish.'); }
try {
  const stop = path.join(logs, 'stop.request');
  if (existsSync(stop)) {
    for (let i = 0; i < 15 && ownedProcess('supervisor'); i++) await delay(500);
    if (ownedProcess('supervisor')) throw Error('Services are still stopping. Try again shortly.');
    unlinkSync(stop);
  }
  if (!ownedProcess('supervisor')) {
    execFileSync(python, [path.join(root, 'scripts/launch_detached.py'), process.execPath], { cwd: root, windowsHide: true, stdio: 'pipe' });
  }
  let ready = false;
  for (let attempt = 0; attempt < 45; attempt++) {
    const status = await health();
    if (status) {
      console.log('ScholarTrace: http://127.0.0.1:8765');
      console.log(status.model_available ? 'Local model ready.' : 'Web ready. Local model is loading or unavailable; evidence search remains usable.');
      if (process.argv.includes('--open')) spawn('explorer.exe', ['http://127.0.0.1:8765'], { windowsHide: true, detached: true, stdio: 'ignore' }).unref();
      ready = true;
      break;
    }
    await delay(500);
  }
  if (!ready) throw Error('Server not ready. Check artifacts/runtime/server.error.log and supervisor.log. Port 8765 may be occupied.');
} finally { closeSync(handle); unlinkSync(lock); }
