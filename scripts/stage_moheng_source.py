"""Update the existing publishing clone, scan new source and preserve history."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/'artifacts/submission-20261021/repository'
ART=ROOT/'artifacts/moheng-final-20261021'
EXCLUDE={'node_modules','dist','__pycache__','.pytest_cache','.git','data','models','tools','output','artifacts'}
EXT={'.py','.mjs','.js','.ts','.tsx','.css','.json','.html','.md','.txt','.yaml','.yml','.svg','.cmd','.ps1','.toml','.ini','.sh'}
PATTERNS=[rb'sk-[A-Za-z0-9_-]{32,}',rb'gh[pousr]_[A-Za-z0-9]{30,}',rb'AKIA[0-9A-Z]{16}',rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----']
def git(*args):
    return subprocess.check_output(['git','-c',f'safe.directory={TARGET.as_posix()}',*args],cwd=TARGET)
if git('status','--porcelain').strip(): raise RuntimeError('Publishing clone has changes; inspect before overwrite')
previous=git('rev-parse','HEAD').decode().strip()
files=[]
for name in ('backend','frontend','scripts','tests','docs','.github','submission-site'):
    for p in (ROOT/name).rglob('*'):
        if p.is_file() and not any(x in EXCLUDE for x in p.relative_to(ROOT).parts):
            if p.suffix.lower() in EXT or (name=='submission-site' and p.suffix=='.png') or p.name=='.nojekyll': files.append(p)
for p in ROOT.iterdir():
    if p.is_file() and (p.suffix in {'.md','.txt','.cmd','.yaml','.ini'} or p.name in {'.env.example','.gitignore','.dockerignore','Dockerfile','Dockerfile.model','LICENSE'}):files.append(p)
secret=json.loads((ROOT/'artifacts/public-review-20261021/review-access.json').read_text('utf-8'))['password'].encode()
for p in files:
    content=p.read_bytes()
    if secret in content or any(re.search(pattern,content) for pattern in PATTERNS):raise RuntimeError('Sensitive content in '+str(p.relative_to(ROOT)))
    dest=TARGET/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
(ART/'source-scan.json').write_text(json.dumps({'previous_commit':previous,'files':len(files),'findings':[],'hashes':hashes,'notice':'Exact reviewer password and common token patterns only; not a comprehensive secret audit.'},ensure_ascii=False,indent=2),encoding='utf-8')
print('Prepared',len(files),'public source files; previous commit',previous)
print(git('diff','--stat').decode('utf-8',errors='replace'))
