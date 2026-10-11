import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import net from 'node:net';

export const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
export const logs = path.join(root, 'artifacts/runtime');
export const python = path.join(root, '.venv/Scripts/python.exe');
export const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const quotePS = value => "'" + value.replaceAll("'", "''") + "'";
export async function health() {
  try {
    const response = await fetch('http://127.0.0.1:8765/api/health', { signal: AbortSignal.timeout(3000) });
    if (!response.ok) return null;
    const data = await response.json();
    return data.service === 'scholartrace' ? data : null;
  } catch { return null; }
}
export function portOpen(port) {
  return new Promise(resolve => {
    const socket = net.connect({ host: '127.0.0.1', port });
    const finish = result => { socket.destroy(); resolve(result); };
    socket.once('connect', () => finish(true));
    socket.once('error', () => finish(false));
    socket.setTimeout(800, () => finish(false));
  });
}
export function ownedProcess(name, kill = false) {
  const record = path.join(logs, name + '.process.json');
  if (!existsSync(record)) return false;
  const { pid, executable, startedAt } = JSON.parse(readFileSync(record, 'utf8'));
  if (!Number.isInteger(pid) || pid <= 0 || !Number.isFinite(startedAt)) throw Error('Invalid process record');
  // Path AND creation time guard against reused PIDs.
  const script = `$p = Get-Process -Id ${pid} -ErrorAction SilentlyContinue; if ($p -and $p.Path -eq ${quotePS(executable)} -and [Math]::Abs(([DateTimeOffset]$p.StartTime).ToUnixTimeMilliseconds() - ${startedAt}) -lt 5000) { ${kill ? `& taskkill.exe /PID ${pid} /T /F | Out-Null; if ($LASTEXITCODE -ne 0 -and (Get-Process -Id ${pid} -ErrorAction SilentlyContinue)) { throw 'Unable to stop project process' };` : ''} 'owned' }; exit 0`;
  return execFileSync('powershell.exe', ['-NoProfile', '-Command', script], { windowsHide: true, encoding: 'utf8' }).trim() === 'owned';
}
