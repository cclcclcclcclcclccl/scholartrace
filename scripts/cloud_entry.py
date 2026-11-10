"""Portable review container lifecycle; credentials come from host secrets."""
import hashlib
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def bootstrap():
    from backend import accounts, database, store
    password = os.environ.get('MOHENG_REVIEW_PASSWORD', '')
    if not 16 <= len(password) <= 200:
        raise ValueError('MOHENG_REVIEW_PASSWORD must contain 16 to 200 characters; configure a platform secret')
    accounts.initialize()
    identifier = hashlib.sha256(b'moheng-cloud-reviewer-v1').hexdigest()[:32]
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    with accounts.connect() as c:
        c.execute('INSERT INTO users VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET salt=excluded.salt,password=excluded.password', (identifier, 'reviewer', salt, digest))
        c.execute('DELETE FROM sessions WHERE user_id=?', (identifier,))
    token = store.database_override.set(accounts.path(identifier))
    try:
        database.initialize()
        for pdf in sorted((store.ROOT / 'seed-papers').glob('*.pdf')):
            store.import_pdf(pdf)
    finally:
        store.database_override.reset(token)
    return identifier


def main():
    # Always use authenticated mode in a publicly reachable review container.
    os.environ['SCHOLARTRACE_PUBLIC'] = '1'
    os.environ['SCHOLARTRACE_REGISTRATION'] = '0'
    os.environ['SCHOLARTRACE_MODEL_URL'] = 'http://127.0.0.1:8081/v1'
    bootstrap()
    env = os.environ.copy()
    env.pop('MOHENG_REVIEW_PASSWORD', None)
    children = []
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        children.append(subprocess.Popen([
            '/opt/llama/llama-server', '-m', str(ROOT / 'models/Qwen3-4B-Q4_K_M.gguf'),
            '--host', '127.0.0.1', '--port', '8081', '-c', '8192', '-np', '1',
            '-t', os.getenv('MOHENG_CPU_THREADS', '2'), '--jinja',
        ], env=env))
        children.append(subprocess.Popen([
            sys.executable, '-m', 'uvicorn', 'backend.app:app', '--host', '0.0.0.0',
            '--port', os.getenv('PORT', '7860'),
        ], cwd=ROOT, env=env))
        while not stopping and all(child.poll() is None for child in children):
            time.sleep(1)
        return 0 if stopping else 1
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == '__main__':
    raise SystemExit(main())
