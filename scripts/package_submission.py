"""Create local submission archives from allowlisted source and evidence files."""
import hashlib,json,zipfile,shutil,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output/submission-20261018';OUT.mkdir(parents=True,exist_ok=True)
SOURCE_EXT={'.py','.mjs','.js','.ts','.tsx','.css','.json','.html','.md','.txt','.yml','.yaml','.svg','.cmd','.ps1','.toml','.ini','.sh'}
EXCLUDED={'node_modules','dist','__pycache__','.pytest_cache','.venv','.git','data','models','tools','output','artifacts'}
def allowed(p):return p.is_file() and not any(x in EXCLUDED for x in p.relative_to(ROOT).parts) and p.suffix.lower() in SOURCE_EXT
source=[]
for name in ['backend','frontend','scripts','tests','docs','.github']:
 if (ROOT/name).exists():source.extend(p for p in (ROOT/name).rglob('*') if allowed(p))
for p in ROOT.iterdir():
 if p.is_file() and (p.name in ['.env.example','.gitignore','.dockerignore','Dockerfile','Dockerfile.model'] or p.suffix.lower() in {'.md','.txt','.cmd','.yml','.toml'}):source.append(p)
patterns=[rb'sk-[A-Za-z0-9_-]{32,}',rb'ghp_[A-Za-z0-9]{30,}',rb'AKIA[0-9A-Z]{16}',rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----']
# Scanner's own literal regex is not a credential; patterns require actual token strings.
for p in source:assert not any(re.search(rx,p.read_bytes()) for rx in patterns),str(p)
def archive(name,files):
 dest=OUT/name
 with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
  for p in sorted(set(files)):z.write(p,p.relative_to(ROOT).as_posix())
 with zipfile.ZipFile(dest) as z:assert z.testzip() is None
 return {'path':dest.name,'files':len(set(files)),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'bytes':dest.stat().st_size}
evidence=[]
for p in (ROOT/'evaluation').rglob('*'):
 if p.is_file() and p.suffix in {'.json','.html','.md'}:evidence.append(p)
for folder in ['proof-v1-first-run','proof-v2-regression','proof-v2-new','proof-v3-regression','proof-v4-qa','proof-v5-qa','proof-v6-qa','proof-v7-qa','module-quality-20261015','module-quality-20261015-repair']:
 for p in (ROOT/'artifacts'/folder).glob('*'):
  if p.is_file() and p.suffix in {'.json','.png','.py'}:evidence.append(p)
for name in ['completion-20261018-tests-final.log','completion-20261018-build.log']:
 evidence.append(ROOT/'artifacts'/name)
for name in ['recording.json','final-browser.json','video-validation.json','history-scan.json','final-preservation.json','pdf-validation.json','release-selection.json','package-browser.json']:
 p=ROOT/'artifacts/submission-20261018'/name
 if p.exists():evidence.append(p)
# Refuse a final package if the final quality round is incomplete.
r=json.loads((ROOT/'artifacts/proof-v7-qa/run.json').read_text('utf-8'));assert r['complete'] and r['original_data_unchanged'];assert (ROOT/'artifacts/proof-v7-qa/agent-source-audit.json').exists()
files=[archive('ScholarTrace-source-20261018.zip',source),archive('ScholarTrace-evidence-20261018.zip',evidence)]
for p in list((ROOT/'output/pdf').glob('*2026-10-18.pdf'))+list((ROOT/'output/video').glob('*')):
 if p.is_file():shutil.copy2(p,OUT/p.name)
for name in ['提交前检查清单_2026-10-18.md','答辩与AI协作说明_2026-10-18.md','本轮修复与交付记录_2026-10-18.md']:
 p=ROOT/'docs'/name
 if p.exists():shutil.copy2(p,OUT/p.name)
manifest=[]
for p in sorted(OUT.iterdir()):
 if p.is_file() and p.name not in ['manifest.json','SHA256SUMS.txt']:manifest.append({'path':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
(OUT/'manifest.json').write_text(json.dumps({'date':'2026-10-18','notice':'Local reviewable submission package. Existing 12-commit history is genuine; current source includes uncommitted work. Not published or submitted. No private DBs, source PDFs or model weights. Basic secret pattern scan only.','archives':files,'files':manifest},ensure_ascii=False,indent=2),'utf-8')
(OUT/'SHA256SUMS.txt').write_text('\n'.join(x['sha256']+'  '+x['path'] for x in manifest)+'\n','utf-8');print(json.dumps(files,ensure_ascii=False));print('PACKAGE',OUT)
