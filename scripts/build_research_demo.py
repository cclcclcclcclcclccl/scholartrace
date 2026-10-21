"""Create a source-backed presentation guide; no invented user-study evidence."""

import ast
import copy
import hashlib
import html
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.answer_contract import checklist

FOLDER = ROOT / "artifacts/research-polish-20261021"


def main():
    old = ROOT / "output/coverage-quality-20261020/ScholarTrace-source-20261020.zip"
    with zipfile.ZipFile(old) as archive:
        previous = ast.parse(archive.read("backend/research.py").decode("utf-8"))
    current = ast.parse((ROOT / "backend/research.py").read_text(encoding="utf-8"))
    before = next(
        n
        for n in previous.body
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "grounded"
    )
    after = copy.deepcopy(
        next(
            n
            for n in current.body
            if isinstance(n, ast.AsyncFunctionDef) and n.name == "_grounded"
        )
    )
    after.name = "grounded"
    assert ast.dump(before) == ast.dump(after), "Generation body must be unchanged"
    rows = []
    for split in ("diagnostic", "confirmation"):
        path = ROOT / f"artifacts/coverage-quality-20261020/candidate4-{split}/run.json"
        run = json.loads(path.read_text(encoding="utf-8"))
        for row in run["rows"]:
            claims = row["response"].get("model_answer") or []
            initial = copy.deepcopy(claims)
            checks = checklist(row["question"], claims)
            assert initial == claims
            rows.append({"case_id": row["case_id"], "answer_checklist": checks})
    (FOLDER / "checklist-replay.json").write_text(
        json.dumps(
            {
                "notice": "Replay of seven exposed saved answers; no new inference, no semantic correctness score. Original generation function AST unchanged apart from its name.",
                "generation_body_unchanged": True,
                "rows": rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    steps = [
        (
            "提出研究问题",
            "选择 Layer Normalization（1607.06450v1.pdf），输入：Layer normalization batch size 1 pure online regime。",
            "我们先验证一个具体判断：batch size 为 1 时能否使用层归一化。",
        ),
        (
            "检查回答要求",
            "展开回答核对清单和相关回答，点击原文入口；尝试“补问：批大小”，核对原问题和当前论文范围后再决定是否发送。",
            "有相关词语不代表已答全。系统将明确要求摆出来，让遗漏更容易被发现。",
        ),
        (
            "保存第一篇证据",
            "定位 PDF 第 2 页关于 pure online regime with batch size 1 的原文，保存证据笔记；记录单样本条件，不写任意任务都更准。",
            "观察与原文一起保存，页码和版本可以追查。",
        ),
        (
            "检查第二篇的机制",
            "切换 On Layer Normalization in the Transformer Architecture（2002.04745v2.pdf），查询 Post-LN Pre-LN expected gradients at initialization warm-up，核对第 1 页并保存笔记。",
            "另一篇讨论归一化的位置、初始化梯度与warm-up；不能把两篇的结论互相代替。",
        ),
        (
            "建立有边界的对照",
            "在证据笔记选择两篇来源建立边界对照。查看比较前检查，点击补齐研究对象；检查数据、指标、条件和限制还有哪些空格。",
            "不会因为同样叫LayerNorm就直接比较。格子填满、单位相同，都不能自动证明科学可比。",
        ),
        (
            "把缺口变成待办",
            "新建包含两篇论文的研究项目，在对照表选择项目，从实验条件空格加入补查，选择本篇原文并回填batch size 1条件。",
            "未找到证据就保留待补查；真实实验条件有出处后再回填，处理历史会保留。",
        ),
        (
            "交付可追查的研究资料",
            "导出项目 ZIP、对照 Markdown 和回答成果。打开文件核对来源、清单、待补项及回填历史。",
            "交付的是可继续检查的研究过程，模型的一次回答只是其中一步。",
        ),
        (
            "展示失败与边界",
            "展示上一轮Pre-LN／Post-LN更新次数互换的失败记录和拒绝实验；指出复杂机制漏答仍未全部解决。",
            "系统已增加有限数字归属防护，但不宣称零幻觉。当前是开发者验证，没有真人省时或满意度结论。",
        ),
    ]
    cards = "".join(
        f'<article class="step" {"" if i == 0 else "hidden"}><small>步骤 {i + 1} / {len(steps)}</small><h2>{html.escape(title)}</h2><h3>操作</h3><p>{html.escape(action)}</p><h3>讲解</h3><p>{html.escape(talk)}</p></article>'
        for i, (title, action, talk) in enumerate(steps)
    )
    document = (
        """<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>研证 · 从问题到可追查证据</title><style>body{margin:0;background:#f4f7f4;color:#213b35;font:17px/1.8 system-ui,sans-serif}main{max-width:860px;margin:auto;padding:32px 22px}h1{line-height:1.35}article{background:white;border:1px solid #d6e4dc;border-radius:18px;padding:28px;margin:24px 0}small{color:#52756a}button,a{display:inline-block;margin:8px 10px 8px 0;padding:10px 16px;border:1px solid #315d50;border-radius:8px;background:white;color:#234c40;font:inherit}button:disabled{opacity:.35}button:focus-visible,a:focus-visible{outline:3px solid #a36723}.notice{border-left:4px solid #a36723;padding-left:16px}[hidden]{display:none}@media(max-width:500px){main{padding:20px 14px}article{padding:18px}h1{font-size:26px}}</style><main><small>SCHOLARTRACE · 真实论文演示指南</small><h1>让每个研究判断，回到它的依据。</h1><p>建议讲解时长5—7分钟，是排练安排，不是实测用户效率。需要已导入两篇源论文并启动本地服务。</p><a href="http://127.0.0.1:8765/" target="_blank" rel="noopener">打开本地作品</a><p class="notice">操作指南不自动写入文库。检查状态只保留在当前页面；模型输出可能变化，遇到缺口应如实展示。</p>"""
        + cards
        + """<nav aria-label="演示步骤"><button id="prev" disabled>上一步</button><button id="next">下一步</button><button id="reset">回到开头</button><span id="status" role="status">第1步，共8步</span></nav><details><summary>来源与验证边界</summary><p>源论文：Layer Normalization，arXiv 1607.06450；On Layer Normalization in the Transformer Architecture，arXiv 2002.04745。页码指本地PDF页码。</p><p>真实浏览器流程记录见同目录验收说明。清单基于显式词语，比较检查基于用户整理的摘录；都不能替代科学判断。没有真实用户研究，没有重新训练模型。</p></details></main><script>let index=0;const steps=[...document.querySelectorAll('.step')];function show(){steps.forEach((s,i)=>s.hidden=i!==index);document.querySelector('#prev').disabled=index===0;document.querySelector('#next').disabled=index===steps.length-1;document.querySelector('#status').textContent=`第${index+1}步，共${steps.length}步`;}document.querySelector('#prev').onclick=()=>{index=Math.max(0,index-1);show()};document.querySelector('#next').onclick=()=>{index=Math.min(steps.length-1,index+1);show()};document.querySelector('#reset').onclick=()=>{index=0;show()};</script></html>"""
    )
    (FOLDER / "演示指南.html").write_text(document, encoding="utf-8")
    guide = "# 研证：从问题到可追查证据\n\n建议5—7分钟，非实测效率。两篇源论文已用于本地开发者走查；模型输出不固定。\n\n"
    for i, (title, action, talk) in enumerate(steps, 1):
        guide += f"## {i}. {title}\n\n操作：{action}\n\n讲解：{talk}\n\n"
    (ROOT / "docs/真实论文演示讲稿_2026-10-21.md").write_text(guide, encoding="utf-8")
    print(
        json.dumps(
            {
                "replayed": len(rows),
                "generation_body_unchanged": True,
                "guide_sha256": hashlib.sha256(document.encode()).hexdigest(),
            }
        )
    )


if __name__ == "__main__":
    main()
