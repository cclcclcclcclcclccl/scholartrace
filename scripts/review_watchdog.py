"""Local review watchdog. No passwords, payments, or OS power changes."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import msvcrt
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / 'artifacts/review-watchdog'
STOP = STATE / 'stop.request'

def now():
    return datetime.now(timezone.utc).isoformat()

def atomic_json(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, path)

def health(url, local=False):
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({})) if local else urllib.request.build_opener()
        with opener.open(url + '/api/health', timeout=12) as response:
            value = json.load(response)
            return {'reachable': value.get('service') == 'scholartrace', 'model_available': bool(value.get('model_available'))}
    except Exception as error:
        return {'reachable': False, 'error': type(error).__name__}

def check():
    try:
        url = (ROOT / 'artifacts/public-review-20261021/url.txt').read_text(encoding='utf-8-sig').strip()
    except OSError:
        url = ''
    public = health(url) if re.fullmatch(r'https://[a-z0-9-]+\.trycloudflare\.com', url) else {'reachable': False, 'error': 'No valid endpoint'}
    return {'checked_at': now(), 'url': url, 'local': health('http://127.0.0.1:8768', True), 'public': public}

def healthy(status):
    return all(status[k].get('reachable') and status[k].get('model_available') for k in ('local', 'public'))

def serve():
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / 'guard.lock').open('a+b') as lock:
        lock.seek(0); lock.write(b'0'); lock.flush(); lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            print('Review watchdog is already running.'); return
        started = now(); failures = 0; last_repair = 0.; samples = 0; failed_samples = 0
        STOP.unlink(missing_ok=True)
        while not STOP.exists():
            status = check(); samples += 1
            ok = healthy(status)
            failures = 0 if ok else failures + 1
            failed_samples += int(not ok)
            status.update(started_at=started, pid=os.getpid(), samples=samples, failed_samples=failed_samples,
                          consecutive_failures=failures, scope='Host-to-public health sampling only; not independent-network or authenticated-user uptime.')
            if failures >= 2 and time.monotonic() - last_repair >= 180:
                status['recovery_started_at'] = now()
                atomic_json(STATE / 'status.json', status)
                last_repair = time.monotonic()
                try:
                    with (STATE / 'recovery.log').open('ab') as log:
                        result = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(ROOT / 'scripts/start_review_host.ps1'), '-UpdateEntry'], cwd=ROOT, stdout=log, stderr=log, timeout=240, creationflags=subprocess.CREATE_NO_WINDOW)
                    status['recovery_exit_code'] = result.returncode
                except subprocess.TimeoutExpired:
                    status['recovery_error'] = 'Recovery timed out; next sample will recheck actual services.'
                except OSError as error:
                    status['recovery_error'] = type(error).__name__
            atomic_json(STATE / 'status.json', status)
            history = STATE / ('health-' + datetime.now(timezone.utc).strftime('%Y%m%d') + '.jsonl')
            with history.open('a',encoding='utf-8') as log:
                log.write(json.dumps(status,ensure_ascii=False)+'\n')
            for _ in range(12):
                if STOP.exists(): break
                time.sleep(5)
        atomic_json(STATE / 'status.json', {'stopped_at': now(), 'started_at': started, 'samples': samples, 'failed_samples': failed_samples, 'stopped': True})

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['start','serve','stop','check']);args=parser.parse_args()
    STATE.mkdir(parents=True,exist_ok=True)
    if args.action=='start':
        STOP.unlink(missing_ok=True)
        subprocess.Popen([sys.executable,'-X','utf8',str(Path(__file__).resolve()),'serve'],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.DETACHED_PROCESS)
        print('Review watchdog launch requested; inspect artifacts/review-watchdog/status.json.')
    elif args.action=='stop':
        STOP.touch();print('Watchdog will stop after its current bounded check. Review services remain running.')
    elif args.action=='check':print(json.dumps(check(),ensure_ascii=False,indent=2))
    else:serve()
if __name__=='__main__':main()
