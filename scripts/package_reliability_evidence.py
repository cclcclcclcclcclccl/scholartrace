"""Package public diagnostic evidence and the final source snapshot, excluding user DBs."""

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "artifacts/ScholarTrace-reliability-evidence.zip"
assert not TARGET.exists(), "Refuse to replace delivered evidence archive"
files = {}


def add(path, name=None):
    p = ROOT / path
    assert p.is_file(), p
    files[name or p.relative_to(ROOT).as_posix()] = p.read_bytes()


for folder in [
    "proof_v1",
    "proof_v2_regression",
    "proof_v2_new",
    "proof_v3_regression",
    "proof_v4_qa",
    "reliability",
    "reliability_study",
]:
    for p in (ROOT / "evaluation" / folder).iterdir():
        if p.suffix in {".json", ".html", ".md"}:
            add(p.relative_to(ROOT))
for folder in [
    "proof-v1-first-run",
    "proof-v2-regression",
    "proof-v2-new",
    "proof-v3-regression",
    "proof-v4-qa",
]:
    for name in [
        "run.json",
        "agent-source-audit.json",
        "original-before.json",
        "original-after.json",
        "comparison-summary.json",
    ]:
        add(Path("artifacts") / folder / name)
for folder in ["reliability-final", "reliability-study"]:
    for p in (ROOT / "artifacts" / folder).iterdir():
        if p.suffix in {".json", ".png"} and p.name != "evidence-package.json":
            add(p.relative_to(ROOT))
for name in [
    "proof-final-tests.log",
    "proof-final-build.log",
    "proof-final-lint.log",
    "proof-v2-regression-console.log",
    "proof-v2-new-console.log",
    "proof-v3-regression-console.log",
    "proof-v4-qa-console.log",
]:
    add(Path("artifacts") / name)
for p in (ROOT / "backend").glob("*.py"):
    add(p.relative_to(ROOT))
for p in (ROOT / "frontend/src").rglob("*"):
    if p.is_file() and p.suffix in {".ts", ".tsx", ".css"}:
        add(p.relative_to(ROOT))
for name in [
    "run_proof_v1.py",
    "proof_metrics.py",
    "build_proof_report.py",
    "build_proof_study.py",
    "score_proof_study.py",
    "build_reliability_report.py",
    "check_reliability_ui.mjs",
    "check_reliability_study.mjs",
    "package_reliability_evidence.py",
    "runtime.mjs",
    "supervisor.mjs",
]:
    add(Path("scripts") / name)
for name in [
    "test_reliability_repairs.py",
    "test_review.py",
    "test_numeric_evidence.py",
    "test_round5.py",
    "test_subquestions.py",
    "test_proof_metrics.py",
]:
    add(Path("tests") / name)
for name in [
    "可靠性修复与质量复验_2026-10-14.md",
    "首轮质量证明与失败分析_2026-10-14.md",
    "需求验收矩阵.md",
]:
    add(Path("docs") / name)
for name in [
    "pyproject.toml",
    "requirements.txt",
    "frontend/package.json",
    "frontend/package-lock.json",
]:
    if (ROOT / name).exists():
        add(name)
add("README.md", "PROJECT-README.md")
files["README.md"] = """# 研证可靠性证据包

先用浏览器打开 evaluation/reliability/report.html，全部210条运行记录及失败均可筛选和展开。

最终结果：48/48受控版本回归、12/12已见真实版本回归；最终12道可答问题9道完整有据，3道虚构私人实验拒答。尚有3题漏答或附加引用问题，具体见 docs/可靠性修复与质量复验_2026-10-14.md。

这些是开发诊断与已见回归，不是独立准确率。问答由开发代理对照原文审查；真人参与者0人，不能宣称省时。

真人工具 evaluation/reliability_study/human-study.html；UI_AUTOMATED_ONLY 是界面测试记录，计分器明确排除，不能当作真人结果。

包含最终源码快照与各轮协议、哈希、输出、审查及浏览器证据。原始模型调用详情保存在项目本机 artifacts/proof-*/model-calls.json，未纳入分享包。本包不含私有数据库、账号、PDF原件与模型权重，也不是可直接运行的整站安装包。复现实推理需要取得合法原文件及对应模型/依赖。历史代码仅有哈希及输出，本包不宣称保存了所有历史源码。

manifest.json 给出每个内容文件的SHA256与大小；文件自身不列入自身清单。ZIP按清单逐项读取验证。
""".encode()
manifest = {
    name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    for name, data in sorted(files.items())
}
files["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2).encode(
    "utf-8"
)
with zipfile.ZipFile(TARGET, "w", zipfile.ZIP_DEFLATED) as z:
    for name, data in files.items():
        z.writestr(name, data)
with zipfile.ZipFile(TARGET) as z:
    assert z.testzip() is None
    assert len(z.namelist()) == len(set(z.namelist())) == len(files)
    for name, entry in manifest.items():
        data = z.read(name)
        assert (
            len(data) == entry["bytes"]
            and hashlib.sha256(data).hexdigest() == entry["sha256"]
        )
result = {
    "path": TARGET.relative_to(ROOT).as_posix(),
    "files": len(files),
    "content_files_verified": len(manifest),
    "bytes": TARGET.stat().st_size,
    "sha256": hashlib.sha256(TARGET.read_bytes()).hexdigest(),
    "contains_private_databases": False,
    "verified": True,
}
(ROOT / "artifacts/reliability-final/evidence-package.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2), "utf-8"
)
print(json.dumps(result, ensure_ascii=False))
