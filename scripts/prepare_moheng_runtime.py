"""Create an isolated final-release test runtime with a consistent DB backup."""
from pathlib import Path
import hashlib
import json
import shutil
import sqlite3

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'artifacts/moheng-final-20261021'
RUNTIME=ART/'runtime'
RUNTIME.mkdir(parents=True,exist_ok=True)
for name in ('backend','tests'):
    shutil.copytree(ROOT/name,RUNTIME/name,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
shutil.copytree(ROOT/'frontend/dist',RUNTIME/'frontend/dist',dirs_exist_ok=True)
shutil.copy2(ROOT/'pytest.ini',RUNTIME/'pytest.ini')
shutil.copytree(ROOT/'data/competition/pdf',RUNTIME/'data/competition/pdf',dirs_exist_ok=True)
shutil.copytree(ROOT/'models/multilingual-minilm',RUNTIME/'models/multilingual-minilm',dirs_exist_ok=True)
db=ROOT/'data/scholartrace.sqlite3'
snapshot={}
with sqlite3.connect(f'file:{db.as_posix()}?mode=ro',uri=True) as conn:
    for name,sql in conn.execute("SELECT name,sql FROM sqlite_master WHERE type='table'"):
        if name.startswith(('sqlite_','block_search')): continue
        rows=conn.execute('SELECT * FROM "'+name.replace('"','""')+'"').fetchall()
        encoded=sorted(json.dumps(list(row),ensure_ascii=False,default=lambda v:v.hex() if isinstance(v,bytes) else str(v)) for row in rows)
        snapshot[name]={'rows':len(rows),'sha256':hashlib.sha256('\n'.join(encoded).encode()).hexdigest()}
    with sqlite3.connect(RUNTIME/'data/scholartrace.sqlite3') as dst: conn.backup(dst)
(ART/'main-data-before.json').write_text(json.dumps(snapshot,indent=2),encoding='utf-8')
print(json.dumps({'runtime':str(RUNTIME),'main_tables':len(snapshot),'private_db_not_for_distribution':True}))
