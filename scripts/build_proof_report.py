"""Build a reproducible evidence report, keeping machine screens and agent audit separate."""

import hashlib
import html
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from proof_metrics import latency, review_metrics

folder = ROOT / "artifacts/proof-v1-first-run"
target = ROOT / "evaluation/proof_v1"
r = json.loads((folder / "run.json").read_text(encoding="utf-8"))
p = json.loads((target / "protocol.json").read_text(encoding="utf-8"))
audit = json.loads((folder / "agent-source-audit.json").read_text(encoding="utf-8"))
assert r["complete"] and r["original_data_unchanged"]
assert (
    r["protocol_sha256"]
    == hashlib.sha256((target / "protocol.json").read_bytes()).hexdigest()
)
assert [c["id"] for c in r["qa"]] == [c["id"] for c in p["qa"]]
for g in ["controlled_review", "real_review"]:
    assert [c["id"] for c in r[g]] == [c["id"] for c in p[g]]
assert {c["id"] for c in audit["cases"]} == {c["id"] for c in p["qa"]}
counts = Counter(c["verdict"] for c in audit["cases"])
summary = {
    "protocol_sha256": r["protocol_sha256"],
    "independent_human_review": False,
    "human_participants": 0,
    "qa_agent_audit": dict(counts),
    "qa_claim_count": sum(
        len(c["claim_supported_by_full_quote"]) for c in audit["cases"]
    ),
    "qa_claims_supported_by_full_quote": sum(
        sum(c["claim_supported_by_full_quote"]) for c in audit["cases"]
    ),
    "qa_citations_exist": sum(
        row["screen"]["claims_with_valid_source"] for row in r["qa"]
    ),
    "qa_latency": latency(r["qa"], "answer_seconds"),
    "preserved_original": r["original_data_unchanged"],
    "review": {
        g: {
            "system": review_metrics(r[g]),
            "baseline": review_metrics(r[g], "baseline"),
            "latency": latency(r[g]),
        }
        for g in ["controlled_review", "real_review"]
    },
    "retrieval": {
        name: {
            "labelled_hits": sum(
                row["retrieval_baselines"][name]["labelled_hits"] for row in r["qa"]
            ),
            "labelled_total": sum(
                row["retrieval_baselines"][name]["labelled_total"] for row in r["qa"]
            ),
        }
        for name in ["lexical", "hybrid"]
    },
}
(folder / "summary.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
)
E = lambda v: html.escape(str(v))
labels = {
    "same_claim": "未变",
    "claim_changed": "变化",
    "unclear": "不确定",
    "unavailable": "未取得判断",
}
htmlrows = []
auditmap = {c["id"]: c for c in audit["cases"]}
for c, row in zip(p["qa"], r["qa"]):
    a = auditmap[c["id"]]
    failed = a["verdict"] not in ["complete_supported", "correct_abstention"]
    claims = row["response"].get("model_answer") or []
    answer = (
        "".join(
            "<article><strong>"
            + E(x["text"])
            + "</strong><blockquote>"
            + E(x["quote"])
            + "</blockquote><small>"
            + E(x["document_id"])
            + " · PDF "
            + E(x["page"])
            + "</small></article>"
            for x in claims
        )
        or "<p>未输出可核对回答。</p>"
    )
    htmlrows.append(
        f'<details class="case" data-failed="{int(failed)}"><summary><span class="tag">问答</span> {E(c["id"])} · {E(c["question"])}</summary><p><b>代理审查：</b>{E(a["rationale"])}</p><p><b>预先标准：</b>{E(c["expected"])}</p>{answer}<p>回答耗时 {row["answer_seconds"]:.2f} 秒；机械筛查与人工解释分别保留。</p></details>'
    )
for g in ["controlled_review", "real_review"]:
    for c, row in zip(p[g], r[g]):
        item = row["input"]
        prediction = row["prediction"]
        new = item.get("candidate", {})
        failed = prediction != row["expected"]
        htmlrows.append(
            f'<details class="case" data-failed="{int(failed)}"><summary><span class="tag">{"受控反例" if g == "controlled_review" else "已见真实回归"}</span> {E(c["id"])} · 标准 {labels[row["expected"]]} / 研证 {labels[prediction]}</summary><p><b>关注：</b>{E(c["observation"])}</p><div class="pair"><blockquote>{E(item["note"]["quote"])}</blockquote><blockquote>{E(new.get("text", "未定位"))}</blockquote></div><p><b>系统理由：</b>{E(row.get("result", {}).get("reason", ""))}</p><p>文本差异基线：{labels[row["baseline"]]}；耗时 {row["seconds"]:.2f} 秒</p></details>'
        )
page = """<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>研证质量证据 · 首轮冻结诊断</title><style>body{background:#f4f6f0;color:#193c35;font:16px/1.75 system-ui,sans-serif;margin:0}main{max-width:1180px;margin:auto;padding:32px}h1{font-size:32px;margin-bottom:5px}h2{font-size:22px}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.card,details{border:1px solid #d4dfd3;background:white;border-radius:12px;padding:20px;margin:14px 0}.value{font-size:32px;font-weight:750}.muted{color:#536a60}.warning{background:#fff2d9;border-left:5px solid #aa651f;padding:18px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}blockquote{margin:12px 0;padding:14px;border-left:3px solid #92af95;background:#f2f5ef;white-space:pre-wrap;overflow-wrap:anywhere}.tag{font-size:13px;color:#496458;background:#e8eee4;padding:4px 7px;border-radius:4px}summary{cursor:pointer;font-weight:650}table{width:100%;border-collapse:collapse;margin:20px 0;background:white}td,th{padding:12px;border:1px solid #d3ddd2;text-align:left}input,button{font:inherit;padding:9px;margin:8px 4px}small{overflow-wrap:anywhere}article{margin:22px 0}a{color:#1b6551}img{max-width:100%}@media(max-width:700px){main{padding:14px}.cards,.pair{grid-template-columns:1fr}table{font-size:13px}}</style><main><p class="muted">SCHOLARTRACE · FROZEN FIRST-PASS DIAGNOSTIC · 2026-10-14</p><h1>质量证据，而非完成度宣传</h1><p>题集、标签和代码在推理前冻结；首次结果与失败完整保留。开发者编题、代理审查，尚无独立人工认证。</p><div class="warning"><strong>当前结论：部分价值获得支持，可靠性仍未达标。</strong><br>不能把引用存在当作回答正确，不能把拒答当作已知答案的正确结果；本页没有真人省时结论。</div><div class="cards"><div class="card"><span class="value">19 / 24</span><p>受控版本三分类正确<br>简单文本差异基线 12 / 24</p></div><div class="card"><span class="value">4 / 7</span><p>可回答题完整且有支持<br>另有 2 / 2 虚构实验题正确拒答</p></div><div class="card"><span class="value">0 人</span><p>真人效用实验尚未收集<br>不得宣称节省 XX% 时间</p></div></div><h2>同样的样例，两种方法</h2><table><tr><th>范围 / 指标</th><th>纯文本差异基线</th><th>研证</th></tr><tr><td>受控反例：严格正确数</td><td>12 / 24</td><td>19 / 24</td></tr><tr><td>受控反例：10 条未变中的误报变化</td><td>8 / 10</td><td>1 / 10，另 1 条不确定</td></tr><tr><td>受控反例：证据不足却确定判断</td><td>4 / 4</td><td>3 / 4</td></tr><tr><td>已见真实版本：严格正确数</td><td>8 / 12</td><td>12 / 12</td></tr><tr><td>问答引用存在 / 引文支持全部内容</td><td colspan="2">9 / 9 引用存在，但仅 8 / 9 完整论断获原文支持（代理审查）</td></tr></table><p>真实版本样例已用于过去开发，不能作为独立泛化准确率。单位换算、缺失证据和条件范围仍有失败。“可减少待复核条目”只是代理指标，并非真人时间收益。</p><h2>可复查材料</h2><p><a href="protocol.json">冻结题集与标准</a> · <a href="freeze.json">协议与代码哈希</a> · <a href="../../artifacts/proof-v1-first-run/run.json">首次完整输出</a> · <a href="../../artifacts/proof-v1-first-run/agent-source-audit.json">逐条代理审查</a> · <a href="human-study.html">真人对照实验工具</a></p><h2>逐题检查</h2><label>筛选 <input id="search" placeholder="题目、原文、错误类型"></label><label><input id="failures" type="checkbox"> 只看未完全通过项</label><p id="count"></p>__ROWS__<p class="muted">所有统计都限于本页冻结样本。后台测试通过数、模型生成速度、真人正确率与科研质量是不同指标。</p></main><script>const all=[...document.querySelectorAll('.case')];function filter(){const q=document.getElementById('search').value.toLowerCase(),fail=document.getElementById('failures').checked;for(const e of all)e.hidden=!(e.textContent.toLowerCase().includes(q)&&(!fail||e.dataset.failed==='1'));document.getElementById('count').textContent='显示 '+all.filter(e=>!e.hidden).length+' / '+all.length+' 条'}document.getElementById('search').oninput=filter;document.getElementById('failures').onchange=filter;filter();</script></html>"""
(target / "report.html").write_text(
    page.replace("__ROWS__", "\n".join(htmlrows)), encoding="utf-8"
)
print(json.dumps(summary, ensure_ascii=False, indent=2))
