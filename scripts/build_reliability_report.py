"""Build a complete multi-round evidence dashboard without selecting successful runs."""

import hashlib
import html
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from proof_metrics import latency, review_metrics

ROUNDS = [
    (
        "v20-old",
        "最终：原句复核与同源用途补全·旧题15项",
        "proof_v20_old",
        "proof-v20-old",
    ),
    (
        "v20-known",
        "最终：原句复核与同源用途补全·开发题6项",
        "proof_v20_known",
        "proof-v20-known",
    ),
    (
        "v20-transfer",
        "最终：原句复核与同源用途补全·跨论文6项",
        "proof_v20_transfer",
        "proof-v20-transfer",
    ),
    ("v19-old", "原句复核与同源用途补全·旧题15项", "proof_v19_old", "proof-v19-old"),
    (
        "v19-known",
        "原句复核与同源用途补全·开发题6项",
        "proof_v19_known",
        "proof-v19-known",
    ),
    (
        "v19-transfer",
        "原句复核与同源用途补全·跨论文6项",
        "proof_v19_transfer",
        "proof-v19-transfer",
    ),
    (
        "v18-old",
        "已拒绝并中断：用途补全范围过宽·旧题",
        "proof_v18_old",
        "proof-v18-old",
    ),
    ("v17-old", "中间候选：原句定位复核·旧题15项", "proof_v17_old", "proof-v17-old"),
    (
        "v17-known",
        "中间候选：原句定位复核·开发题6项",
        "proof_v17_known",
        "proof-v17-known",
    ),
    (
        "v17-transfer",
        "中间候选：原句定位复核·跨论文6项",
        "proof_v17_transfer",
        "proof-v17-transfer",
    ),
    ("v16-old", "直接陈述与采样条件选段·旧题15项", "proof_v16_old", "proof-v16-old"),
    (
        "v16-known",
        "直接陈述与采样条件选段·开发题6项",
        "proof_v16_known",
        "proof-v16-known",
    ),
    (
        "v16-transfer",
        "直接陈述与采样条件选段·跨论文6项",
        "proof_v16_transfer",
        "proof-v16-transfer",
    ),
    ("v15-old", "明确原文范围与比较上下文·旧题15项", "proof_v15_old", "proof-v15-old"),
    (
        "v15-known",
        "明确原文范围与比较上下文·开发题6项",
        "proof_v15_known",
        "proof-v15-known",
    ),
    (
        "v15-transfer",
        "明确原文范围与比较上下文·跨论文6项",
        "proof_v15_transfer",
        "proof-v15-transfer",
    ),
    ("v14-old", "思考限额与单日期核验·旧题15项", "proof_v14_old", "proof-v14-old"),
    (
        "v14-known",
        "思考限额与单日期核验·开发题6项",
        "proof_v14_known",
        "proof-v14-known",
    ),
    (
        "v14-transfer",
        "思考限额与单日期核验·跨论文6项",
        "proof_v14_transfer",
        "proof-v14-transfer",
    ),
    ("v13-old", "未采用宽泛日期等价候选·旧题15项", "proof_v13_old", "proof-v13-old"),
    (
        "v13-known",
        "未采用宽泛日期等价候选·开发题6项",
        "proof_v13_known",
        "proof-v13-known",
    ),
    (
        "v13-transfer",
        "未采用宽泛日期等价候选·跨论文6项",
        "proof_v13_transfer",
        "proof-v13-transfer",
    ),
    ("v12-old", "未采用思考限额候选·旧题15项", "proof_v12_old", "proof-v12-old"),
    ("v12-known", "未采用思考限额候选·开发题6项", "proof_v12_known", "proof-v12-known"),
    (
        "v12-transfer",
        "未采用思考限额候选·跨论文6项（含规划失败）",
        "proof_v12_transfer",
        "proof-v12-transfer",
    ),
    (
        "v10-confirm-known",
        "恢复采用实现·开发题6项复跑",
        "proof_v10_confirm_known",
        "proof-v10-confirm-known",
    ),
    (
        "v10-confirm-old",
        "恢复采用实现·旧题15项复跑",
        "proof_v10_confirm_old",
        "proof-v10-confirm-old",
    ),
    (
        "v11-planner-known",
        "未采用规划约束·开发题6项",
        "proof_v11_selected_known",
        "proof-v11-selected-known",
    ),
    (
        "v11-planner-old",
        "未采用规划约束·旧题15项（含推理失败）",
        "proof_v11_selected_old",
        "proof-v11-selected-old",
    ),
    (
        "v11-candidate-transfer",
        "未采用新版4B·跨论文6项",
        "proof_v11_candidate_transfer",
        "proof-v11-candidate-transfer",
    ),
    (
        "v11-candidate-known",
        "未采用新版4B·开发题6项",
        "proof_v11_candidate_known",
        "proof-v11-candidate-known",
    ),
    (
        "v11-candidate-old",
        "未采用新版4B·旧题15项",
        "proof_v11_candidate_old",
        "proof-v11-candidate-old",
    ),
    (
        "v11-base",
        "规划修复后原模型·跨论文6项",
        "proof_v11_transfer_base",
        "proof-v11-transfer-base",
    ),
    (
        "v10-transfer",
        "信息流修复·跨论文6项（含推理失败）",
        "proof_v10_transfer",
        "proof-v10-transfer",
    ),
    ("v10-known", "信息流修复·开发题6项", "proof_v10_known", "proof-v10-known"),
    ("v10-old", "信息流修复·旧题15项", "proof_v10_old", "proof-v10-old"),
    (
        "v10-base",
        "原版本·跨论文6项（含推理失败）",
        "proof_v10_transfer_baseline",
        "proof-v10-transfer-baseline",
    ),
    ("v9-new", "未采用范围修订·新增开发题6项", "proof_v9_new", "proof-v9-new"),
    ("v9-old", "未采用范围修订·旧题15项", "proof_v9_regression", "proof-v9-regression"),
    ("v8-old", "未采用中文审核·旧题15项", "proof_v8_regression", "proof-v8-regression"),
    (
        "v8-baseline",
        "原版本·新增开发题6项",
        "proof_v8_baseline_new",
        "proof-v8-baseline-new",
    ),
    ("v7", "未采用推理审核·已见问答15项", "proof_v7_qa", "proof-v7-qa"),
    ("v6", "上轮交付审核版本·已见问答15项", "proof_v6_qa", "proof-v6-qa"),
    ("v5", "引用与对象修复·已见问答15项", "proof_v5_qa", "proof-v5-qa"),
    ("v4", "最终安全修复·已见问答15项", "proof_v4_qa", "proof-v4-qa"),
    ("v1", "首轮45项", "proof_v1", "proof-v1-first-run"),
    ("v2-old", "第一轮修复·旧题45项", "proof_v2_regression", "proof-v2-regression"),
    ("v2-new", "第一轮修复·新冻结30项", "proof_v2_new", "proof-v2-new"),
    ("v3", "最终修复·已见75项回归", "proof_v3_regression", "proof-v3-regression"),
]
E = lambda x: html.escape(str(x), quote=True)
VERDICTS = {
    "complete_with_unsupported_claim": "主要问题已答但含无据论断",
    "complete_supported": "完整且引用有据",
    "partial_supported": "部分回答有据",
    "partial_with_unsupported_qualifier": "部分回答含无据限定",
    "answerable_abstention": "可回答但拒答",
    "unsupported_and_incomplete": "错误或无据且不完整",
    "correct_abstention": "正确拒绝虚构实验",
}


def main():
    target = ROOT / "evaluation/reliability"
    target.mkdir(exist_ok=True)
    summaries = []
    cards = []
    for key, label, protocol_dir, result_dir in ROUNDS:
        folder = ROOT / "artifacts" / result_dir
        r = json.loads((folder / "run.json").read_text("utf-8"))
        protocol = ROOT / "evaluation" / protocol_dir / "protocol.json"
        p = json.loads(protocol.read_text("utf-8"))
        audit = json.loads((folder / "agent-source-audit.json").read_text("utf-8"))
        trace = json.loads((folder / "model-calls.json").read_text("utf-8"))
        call_errors = [c for c in trace if c.get("error")]
        aborted = None
        if not r["complete"]:
            aborted = json.loads((folder / "aborted.json").read_text("utf-8"))
            assert aborted["status"] == "aborted" and aborted["original_data_unchanged"]
        else:
            assert r["original_data_unchanged"]
        assert r["protocol_sha256"] == hashlib.sha256(protocol.read_bytes()).hexdigest()
        amap = {x["id"]: x for x in audit["cases"]}
        assert set(amap) == {x["id"] for x in r["qa"]}
        counts = Counter(x["verdict"] for x in audit["cases"])
        summary = {
            "key": key,
            "label": label,
            "notice": r["notice"],
            "protocol_sha256": r["protocol_sha256"],
            "qa_total": len(r["qa"]),
            "qa_expected": len(p["qa"]),
            "complete": r["complete"],
            "aborted_reason": aborted["reason"] if aborted else None,
            "qa_answerable": sum(not x["unanswerable"] for x in p["qa"]),
            "qa_audit": dict(counts),
            "claims": sum(
                len(x["claim_supported_by_full_quote"]) for x in audit["cases"]
            ),
            "supported_claims": sum(
                sum(x["claim_supported_by_full_quote"]) for x in audit["cases"]
            ),
            "qa_latency": latency(r["qa"], "answer_seconds"),
            "model_file": r.get("model_file", "models/Qwen3-4B-Q4_K_M.gguf"),
            "model_file_sha256": r.get("model_file_sha256"),
            "model_call_error_count": len(call_errors),
            "original_data_unchanged": True,
            "human_participants": 0,
            "review": {
                g: {
                    "system": review_metrics(r[g]),
                    "baseline": review_metrics(r[g], "baseline"),
                }
                for g in ["controlled_review", "real_review"]
            },
        }
        summaries.append(summary)
        for group in ["qa", "controlled_review", "real_review"]:
            expected = p[group][: len(r[group])] if aborted else p[group]
            assert [x["id"] for x in r[group]] == [x["id"] for x in expected]
            for case, row in zip(p[group], r[group]):
                if group == "qa":
                    a = amap[row["id"]]
                    failed = a["verdict"] not in [
                        "complete_supported",
                        "correct_abstention",
                    ]
                    claims = row.get("response", {}).get("model_answer") or []
                    assert len(claims) == len(a["claim_supported_by_full_quote"])
                    body = f"<p><b>预先标准：</b>{E(case['expected'])}</p><p><b>代理审查：</b>{E(a['rationale'])}</p>"
                    for c, supported in zip(claims, a["claim_supported_by_full_quote"]):
                        body += f"<article><b>{E(c['text'])}</b><p>完整引用支持：{'是' if supported else '否'} · PDF页 {E(c['page'])} · 文献 {E(c['document_id'])}</p><blockquote>{E(c['quote'])}</blockquote><p>模型选择的短支持片段：{E(c.get('support_span', ''))}</p></article>"
                    if not claims:
                        body += "<p>未返回通过初筛的回答；不代表论文没有答案。</p>"
                    body += f"<p>耗时：{E(row.get('answer_seconds', '失败'))}秒。机械筛查：{E(row.get('screen', {}))}</p>"
                    title = case["question"]
                    status = VERDICTS.get(a["verdict"], a["verdict"])
                    errors = [
                        c["error"] for c in call_errors if c.get("case_id") == row["id"]
                    ]
                    if errors or row.get("error"):
                        failed = True
                        status += " · 推理失败/降级（不计完整通过）"
                        body += f"<p class='notice'>调用错误：{E(errors or row.get('error'))}</p>"
                else:
                    failed = row["prediction"] != row["expected"]
                    item = row.get("input", {})
                    result = row.get("result", {})
                    body = f'<p>预期：{E(row["expected"])} · 实际：{E(row["prediction"])} · 文本基线：{E(row.get("baseline"))}</p><p>{E(result.get("reason", row.get("error", "")))}</p><div class="pair"><blockquote>{E(item.get("note", {}).get("quote", ""))}</blockquote><blockquote>{E((item.get("candidate") or {}).get("text", ""))}</blockquote></div><p>耗时 {E(row.get("seconds"))} 秒 · 方法 {E(result.get("method", "本地模型"))}</p>'
                    title = case["observation"]
                    status = "不符合预期" if failed else "符合预期"
                if aborted:
                    failed = True
                    status += " · 批次已中断，不计完整批次成绩"
                    body += f"<p class='notice'>中断原因：{E(aborted['reason'])}</p>"
                cards.append(
                    f'<details class="case" data-round="{key}" data-failed="{int(failed)}"><summary><span class="tag">{E(label)}</span> {E(row["id"])} · {E(status)}<br>{E(title)}</summary>{body}</details>'
                )
        (folder / "comparison-summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), "utf-8"
        )
    (target / "summary.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2), "utf-8"
    )
    ratio = lambda a, b: f"{a}/{b}" if b else "本轮未测"
    table = ""
    for s in summaries:
        if not s["complete"]:
            table += f"<tr><td>{E(s['label'])}</td><td colspan='6'>已中断；完成并审阅 {s['qa_total']}/{s['qa_expected']} 题，不计完整批次成绩。{E(s['aborted_reason'])}</td></tr>"
            continue
        m = s["review"]["controlled_review"]["system"]
        b = s["review"]["controlled_review"]["baseline"]
        q = s["qa_audit"]
        table += f"<tr><td>{E(s['label'])}</td><td>{ratio(m['exact_correct'], m['n'])}</td><td>{ratio(b['exact_correct'], b['n'])}</td><td>{ratio(m['unsupported_decisive_on_unclear'], m['expected_unclear'])}</td><td>{q.get('complete_supported', 0)}/{s['qa_answerable']}</td><td>{s['supported_claims']}/{s['claims']}</td><td>{s['model_call_error_count']}</td></tr>"
    page = (
        """<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>研证 · 质量证据与修复记录</title><style>
 :root{font-family:system-ui,"Microsoft YaHei",sans-serif;color:#193033;background:#f3f6f5}body{max-width:1120px;margin:auto;padding:36px 24px;line-height:1.7}h1{font-size:34px;line-height:1.3}header{border-top:5px solid #267d71;padding-top:18px}.eyebrow{color:#276e63;letter-spacing:2px}.notice{background:#fff5dc;padding:16px;border-radius:12px}.stats{overflow:auto;background:white;border-radius:12px}table{border-collapse:collapse;width:100%;min-width:760px}th,td{text-align:left;padding:13px;border-bottom:1px solid #dce5e1}th{color:#316258}nav{display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin:24px 0}select,input{font:inherit;padding:8px;border:1px solid #aac3bb;border-radius:8px;max-width:100%;box-sizing:border-box}input[type=search]{flex:1;min-width:180px}.case{background:white;border:1px solid #dce5e1;border-radius:12px;margin:12px 0;padding:16px;overflow-wrap:anywhere}.case[data-failed="1"]{border-left:5px solid #b96b37}summary{cursor:pointer;font-weight:600}.tag{font-size:12px;color:#397466}blockquote{border-left:3px solid #b7cbc2;padding:12px;margin:12px 0;background:#f7faf8;white-space:pre-wrap;font-size:14px}article{margin:18px 0;padding-top:12px;border-top:1px solid #dce5e1}.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}a{color:#17685d}button{font:inherit;border:1px solid #aac3bb;border-radius:8px;padding:8px;background:white;cursor:pointer}[hidden]{display:none!important}@media(max-width:600px){body{padding:22px 14px}h1{font-size:27px}.pair{grid-template-columns:1fr}nav{align-items:stretch}select{width:100%}}
 </style><header><div class="eyebrow">SCHOLARTRACE / 可核对的证据</div><h1>修复了什么，仍然会错在哪里</h1><p>保留每轮首次输出、失败候选和模型调用错误。本轮关注正确答案误拒、支持句错配及处理用途遗漏。完整回归与主动中断的候选分开标记，中断批次不计完整成绩。所有结果仅限已见开发题；实际采用决定见交付目录中的采用版本记录，候选出现在报告中不代表已经上线。</p></header><p class="notice"><b>使用边界：</b>题目由开发代理编写，新增题在推理前冻结；旧题为已见回归，跨论文题覆盖另外5篇论文，仍不是独立评测。下方数量为含重复题的运行记录。问答结论由开发代理对照完整原文审查，尚无独立真人标注。引用真实存在不等于论断准确；没有答案不等于论文未报告。真人参与者为0，不能宣称节省人工时间。出现调用错误的轮次即使有降级答案，也不能视为完整通过。</p><div class="stats"><table><thead><tr><th>运行批次</th><th>受控复核符合预期</th><th>文本基线</th><th>缺证据却确定判断</th><th>可答题完整有据</th><th>论断受完整引用支持</th><th>调用错误</th></tr></thead><tbody>"""
        + table
        + """</tbody></table></div><p>分母包括全部预先冻结案例。正确拒答单独统计，不计入可回答题成功率；受控样例不是随机论文总体。</p><nav aria-label="筛选质量记录"><select id="round" aria-label="选择运行批次"><option value="all">全部批次</option>"""
        + "".join(f'<option value="{k}">{E(l)}</option>' for k, l, _, _ in ROUNDS)
        + """</select><label><input id="failed" type="checkbox"> 仅看失败与不完整</label><input id="search" type="search" aria-label="搜索案例" placeholder="搜索问题、案例编号、原文"><button id="expand">展开当前结果</button></nav><p id="count" aria-live="polite"></p><main>"""
        + "".join(cards)
        + """</main><p><a href="../reliability_study/human-study.html">进入真人计时试验工具（本轮复核提示）</a> · <a href="summary.json">机器可读汇总</a></p><script>
 const $=id=>document.getElementById(id),rows=[...document.querySelectorAll('.case')];function filter(){let n=0;for(const r of rows){r.hidden=($('round').value!=='all'&&r.dataset.round!==$('round').value)||($('failed').checked&&r.dataset.failed!=='1')||!r.textContent.toLowerCase().includes($('search').value.toLowerCase());if(!r.hidden)n++}$('count').textContent=`显示 ${n} / ${rows.length} 项；所有批次与失败均保留。`;}['round','failed','search'].forEach(id=>$(id).addEventListener('input',filter));$('expand').onclick=()=>rows.filter(r=>!r.hidden).forEach(r=>r.open=true);filter();</script></html>"""
    )
    (target / "report.html").write_text(page, "utf-8")
    print(json.dumps(summaries, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
