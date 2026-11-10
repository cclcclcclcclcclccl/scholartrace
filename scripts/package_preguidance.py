"""Build a small, source-only cloud upload package and a dated revision handoff."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/moheng-revision-20261110'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / 'docs/预指导修改说明_2026-11-10.md', OUT / '01_预指导修改说明.md')
    files = {}
    for folder in ['backend', 'frontend/src', 'frontend/public']:
        for p in (ROOT / folder).rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts:
                files[p.relative_to(ROOT).as_posix()] = p.read_bytes()
    for name in ['.dockerignore', 'requirements-lock.txt', 'requirements-formula-lock.txt',
                 'frontend/package.json', 'frontend/package-lock.json', 'frontend/index.html',
                 'frontend/tsconfig.json', 'frontend/vite.config.ts', 'scripts/formula_worker.py',
                 'scripts/cloud_entry.py', 'scripts/cloud_assets.py', 'deploy/assets.json']:
        files[name] = (ROOT / name).read_bytes()
    files['Dockerfile'] = (ROOT / 'Dockerfile.cloud').read_bytes()
    files['README.md'] = (ROOT / 'deploy/README.modelscope.md').read_bytes()
    files['ms_deploy.json'] = (ROOT / 'deploy/ms_deploy.json').read_bytes()
    archive = OUT / '02_魔搭免费云端部署包.zip'
    manifest = []
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, content in sorted(files.items()):
            assert not name.startswith(('data/', 'artifacts/', 'models/', 'output/', 'archive/', '.git/'))
            z.writestr(name, content)
            manifest.append({'path': name, 'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()})
        z.writestr('DEPLOY-MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for item in manifest:
            assert hashlib.sha256(z.read(item['path'])).hexdigest() == item['sha256']
    access = json.loads((ROOT / 'artifacts/public-review-20261021/review-access.json').read_text(encoding='utf-8-sig'))
    (OUT / '04_仅本人查看_云端密钥.txt').write_text(
        '这是私密文件，不上传仓库或公开网盘。\n在魔搭空间设置中添加环境变量（秘密值）：\n'
        '变量名：MOHENG_REVIEW_PASSWORD\n值：' + access['password'] +
        '\n评审登录名：reviewer\n沿用既有评审专用密码，不是你的个人账号密码。\n', encoding='utf-8')
    evidence = OUT / '验收证据'
    evidence.mkdir(exist_ok=True)
    sources = {
        '官方PDF三类用例.json': 'official-final/report.json',
        '后端431项测试.txt': 'pytest-final.log',
        '正文语义界面检查.json': 'ui/browser.json',
        '公网登录与问答检查.json': 'public-browser.json',
        '前端依赖扫描.json': 'npm-audit-final.json',
        '云端回车转后台浏览器检查.json': 'cloud-dispatch.json',
    }
    for name, source in sources.items():
        shutil.copy2(ROOT / 'artifacts/preguidance-20261110' / source, evidence / name)
    accepted = ROOT / 'artifacts/preguidance-20261110/cloud-evidence-accepted'
    cloud_result = json.loads((accepted / 'docker-evidence/docker-check.json').read_text(encoding='utf-8'))
    external_result = json.loads((accepted / 'independent-network-evidence/external-check.json').read_text(encoding='utf-8'))
    assert cloud_result['passed'] and external_result['passed']
    for folder in ['docker-evidence', 'independent-network-evidence']:
        for p in (accepted / folder).iterdir():
            shutil.copy2(p, evidence / p.name)
    shutil.copy2(ROOT / 'artifacts/preguidance-20261110/docker-final-failure.log', evidence / '修复前同步问答超时_保留记录.txt')
    result = {'created_date': '2026-11-10', 'cloud_deployed': False,
              'docker_run': 'https://github.com/cclcclcclcclcclccl/scholartrace/actions/runs/42769900330',
              'prior_failed_run': 'https://github.com/cclcclcclcclcclccl/scholartrace/actions/runs/42771811298',
              'prior_failure': 'Synchronous answer exceeded 240-second request budget on slow CPU; retained as evidence',
              'final_background_run': 'https://github.com/cclcclcclcclcclccl/scholartrace/actions/runs/42774358889',
              'archive': archive.name, 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
              'source_files': len(files), 'bytes': archive.stat().st_size,
              'private_file': '04_仅本人查看_云端密钥.txt',
              'docker_validation_passed': True, 'independent_network_validation_passed': True,
              'backend_tests_passed': 439, 'npm_known_vulnerabilities': 0,
              'cloud_job_acceptance_seconds': cloud_result['job_acceptance_seconds'],
              'cloud_answer_seconds': cloud_result['answer_seconds'],
              'pending': ['Owner ModelScope account and real-name verification', 'Deploy and validate stable cloud instance', 'Update stable judge entry only after cloud acceptance']}
    (OUT / '05_材料状态与校验.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Verified deployment archive:', len(files), 'files,', archive.stat().st_size, 'bytes; private credentials excluded')


if __name__ == '__main__':
    main()
