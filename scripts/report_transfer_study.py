"""Publish transparent case-level developer judgments alongside original answers."""

import html
import json
import statistics
from collections import Counter

from transfer_study import ARTIFACTS, PROTOCOL, digest, write

LABELS = {"direct": "模型直接回答", "rag": "普通检索问答", "product": "研证完整流程"}
STATUS = {
    "complete": "完整通过",
    "partial": "部分正确/遗漏",
    "wrong": "实质错误",
    "correct_abstention": "正确拒答",
    "error": "运行失败",
}


def main():
    protocol = json.loads(PROTOCOL.read_text("utf-8"))
    review_path = PROTOCOL.parent / "review.json"
    reviews = json.loads(review_path.read_text("utf-8"))
    rows, runs = [], {}
    for name in ("diagnostic-first", "diagnostic-candidate1", "confirmation-first"):
        run = json.loads((ARTIFACTS / name / "run.json").read_text("utf-8"))
        assert run["complete"] and run["original_unchanged"]
        assert run["protocol_sha256"] == digest(PROTOCOL)
        runs[name] = run
        for row in run["rows"]:
            status, rationale = reviews[name][row["case_id"]][row["method"]]
            if row.get("error"):
                assert status == "error"
            rows.append(
                {"run": name, **row, "review_status": status, "rationale": rationale}
            )
    assert (
        runs["diagnostic-candidate1"]["code_sha256"]
        == runs["confirmation-first"]["code_sha256"]
    )
    summary = {}
    for method in LABELS:
        chosen = [
            r
            for r in rows
            if r["method"] == method
            and r["run"]
            in (
                "diagnostic-candidate1" if method == "product" else "diagnostic-first",
                "confirmation-first",
            )
        ]
        assert len(chosen) == 7
        summary[method] = {
            "total": len(chosen),
            "grades": dict(Counter(r["review_status"] for r in chosen)),
            "median_seconds": round(statistics.median(r["seconds"] for r in chosen), 3),
            "model_calls": sum(r["model_calls"] for r in chosen),
        }
    report = {
        "notice": reviews["notice"],
        "scope": "四道开发诊断题加三道保留确认题；合计不是独立准确率。直接模型、RAG与产品并非等调用成本；无重复计时或统计显著性判断。",
        "summary": summary,
        "rows": rows,
        "protocol_sha256": digest(PROTOCOL),
        "reviews_sha256": digest(review_path),
    }
    write(ARTIFACTS / "comparison.json", report)
    esc = html.escape
    parts = [
        """<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>研证 · 真实论文对照记录</title>
<style>body{font:16px/1.75 system-ui,sans-serif;background:#f4f7f5;color:#172d29;margin:0}main{max-width:1100px;margin:auto;padding:36px 20px}h1{font-size:30px}article,.notice,table{background:white;border:1px solid #d4e2db;border-radius:12px;padding:20px;margin:20px 0}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:12px;border-bottom:1px solid #ddd}pre,blockquote{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.7 system-ui;background:#f2f5f3;padding:16px}select,input{font:inherit;padding:8px;max-width:100%;margin:5px}summary{cursor:pointer;color:#256453}small{color:#526a61}article[hidden]{display:none}.wrong{border-left:5px solid #a64444}.partial{border-left:5px solid #b48633}.complete,.correct_abstention{border-left:5px solid #34765f}@media(max-width:650px){table{display:block;overflow:auto}}</style><main><h1>研证 · 真实论文对照记录</h1>
<p>先保留失败，再验证修复。你可以查看每一道题的完整回答、原文标准、耗时与开发者判断。</p>""",
        '<div class="notice">'
        + esc(report["notice"] + " " + report["scope"])
        + "</div>",
        "<table><tr><th>方法</th><th>完整/正确拒答</th><th>部分回答</th><th>实质错误</th><th>调用总数</th><th>耗时中位数</th></tr>",
    ]
    for method, data in summary.items():
        counts = data["grades"]
        passed = counts.get("complete", 0) + counts.get("correct_abstention", 0)
        parts.append(
            f"<tr><td>{LABELS[method]}</td><td>{passed}/7</td><td>{counts.get('partial', 0)}</td><td>{counts.get('wrong', 0)}</td><td>{data['model_calls']}</td><td>{data['median_seconds']} 秒</td></tr>"
        )
    parts += [
        "</table><p>诊断题：研证由1/4完整通过改善到2/4。保留确认题：普通检索问答3/3，研证2/3；研证的跨论文回答仍遗漏细节。以上是小样本开发记录，不能宣称全面领先。</p>",
        '<label>方法 <select id="method"><option value="">全部</option>'
        + "".join(f'<option value="{k}">{v}</option>' for k, v in LABELS.items())
        + '</select></label><label>结果 <select id="status"><option value="">全部</option>'
        + "".join(f'<option value="{k}">{v}</option>' for k, v in STATUS.items())
        + '</select></label><label>搜索 <input id="search" placeholder="题目、回答或评审说明"></label><p id="count" aria-live="polite"></p>',
    ]
    cases = {c["id"]: c for c in protocol["cases"]}
    for row in rows:
        case = cases[row["case_id"]]
        answer = (
            row.get("answer")
            or row.get("response", {}).get("message")
            or row.get("error")
            or "无回答"
        )
        parts.append(
            f'<article class="{row["review_status"]}" data-method="{row["method"]}" data-status="{row["review_status"]}"><h2>{esc(case["question"])}</h2><small>{esc(row["run"])} · {LABELS[row["method"]]} · {STATUS[row["review_status"]]} · {row["seconds"]}秒 · {row["model_calls"]}次调用</small><p>{esc(row["rationale"])}</p><details><summary>展开原始回答与冻结标准</summary><pre>{esc(answer)}</pre><strong>冻结原文标准</strong><ul>'
            + "".join("<li>" + esc(fact) + "</li>" for fact in case["gold_facts"])
            + "</ul>"
        )
        for source in case["sources"]:
            parts.append(
                f"<details><summary>{esc(source['file'])} · PDF第{source['page']}页 · {source['id']}</summary><blockquote>{esc(source['text'])}</blockquote></details>"
            )
        parts.append("</details></article>")
    parts.append(
        """<script>const controls=['method','status','search'].map(id=>document.getElementById(id));function filter(){let n=0;document.querySelectorAll('article').forEach(el=>{const show=(!controls[0].value||el.dataset.method===controls[0].value)&&(!controls[1].value||el.dataset.status===controls[1].value)&&el.textContent.toLowerCase().includes(controls[2].value.toLowerCase());el.hidden=!show;if(show)n++});document.getElementById('count').textContent='当前显示 '+n+' 条记录（含修复前后，不合并为独立题数）'}controls.forEach(el=>el.addEventListener('input',filter));filter();</script></main></html>"""
    )
    (ARTIFACTS / "report.html").write_text("".join(parts), "utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
