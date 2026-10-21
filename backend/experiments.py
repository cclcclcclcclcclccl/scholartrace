"""Editable experiment protocols and transparent statistics from supplied measurements."""

import csv
import hashlib
import io
import json
import math
import re
import zipfile
from typing import Literal

import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from scipy.stats import t

from . import charts, research, store
from .execution_check import AttentionExecution, preflight

router = APIRouter(prefix="/api/experiments")


class Protocol(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    hypothesis: str = Field(min_length=5, max_length=2000)
    task: Literal[
        "classification", "language_modeling", "translation", "retrieval", "other"
    ]
    dataset: str = Field(min_length=2, max_length=1000)
    split: str = Field(min_length=3, max_length=1000)
    baseline: str = Field(min_length=2, max_length=1000)
    variable: str = Field(min_length=2, max_length=1000)
    controls: str = Field(min_length=3, max_length=2000)
    metric: str = Field(min_length=2, max_length=100)
    direction: Literal["higher", "lower"]
    criterion: str = Field(min_length=3, max_length=1000)
    seeds: list[int] = Field(min_length=2, max_length=30)
    resources: str = Field(min_length=2, max_length=1000)
    failure: str = Field(min_length=3, max_length=1000)
    source_artifact_id: str | None = None
    document_ids: list[str] = Field(default_factory=list, max_length=20)
    execution: AttentionExecution | None = None


def check_protocol(spec):
    warnings = []
    if len(set(spec["seeds"])) != len(spec["seeds"]) or any(
        s < 0 or s > 2**32 - 1 for s in spec["seeds"]
    ):
        raise ValueError("随机种子须为 0—4294967295 之间的不同整数")
    for key, value in spec.items():
        if isinstance(value, str) and not value.strip():
            raise ValueError(f"实验字段 {key} 不能为空白")
    if spec["task"] in {
        "classification",
        "language_modeling",
        "retrieval",
    } and re.search(r"\bBLEU\b", spec["metric"], re.IGNORECASE):
        warnings.append("当前任务与 BLEU 指标可能不匹配，请核对数据集的官方评价方法。")
    if (
        re.search(
            r"perplexity|困惑度|交叉熵|loss|耗时|延迟", spec["metric"], re.IGNORECASE
        )
        and spec["direction"] == "higher"
    ):
        warnings.append("该指标通常越低越好，当前却设置为越高越好，请核对优化方向。")
    if any(
        re.search(r"待定|待选择|待测|待确定|TODO", str(v), re.IGNORECASE)
        for v in spec.values()
    ):
        warnings.append(
            "存在待定条件。先确认数据许可、划分、硬件及阈值，再按此卡开展实验。"
        )
    if not re.search(r"官方|固定|\d+\s*%|\d+\s*[:：/]\s*\d+", spec["split"]):
        warnings.append(
            "数据划分不够明确：填写官方固定划分，或具体比例、划分种子与防泄漏规则。"
        )
    if len(spec["seeds"]) < 3:
        warnings.append(
            "仅两次独立运行难以稳定估计波动，建议先做资源试跑，再增加重复次数。"
        )
    if "头" in spec["variable"]:
        warnings.append(
            "调整注意力头数前检查 d_model 与头数整除、投影形状及预训练权重兼容性；固定计算量不等于固定实测耗时。"
        )
    return warnings


def protocol_content(body):
    spec = body.model_dump()
    warnings = check_protocol(spec)
    if body.execution:
        if body.task != "language_modeling":
            warnings.append(
                "当前具体执行模板针对从零训练的注意力语言模型，请核对是否符合所选任务；不会自动改变研究方向。"
            )
        warnings.append(
            "结构化参数只检查取值和维度关系，训练预算、数据许可和科学可行性仍需实测核对。"
        )
    for identifier in spec["document_ids"]:
        store.get_document(identifier)
    source = (
        research.artifact(spec["source_artifact_id"])
        if spec["source_artifact_id"]
        else None
    )
    return {
        "protocol": spec,
        "checks": warnings,
        "source_title": source["title"] if source else None,
        "notice": "人工填写的实验设计；尚未运行。字段检查不证明科学合理性，来源成果只是设计参考。修改卡片会生成新修订，已有测量绑定原修订。",
    }


@router.post("/protocols")
def create_protocol(body: Protocol):
    content = protocol_content(body)
    return research.save_artifact(
        "protocol", body.title, {**content, "revision": 1, "history": []}
    )


class ProtocolEdit(BaseModel):
    protocol: Protocol
    revision: int = Field(ge=1)


@router.put("/protocols/{identifier}")
def edit_protocol(identifier: str, body: ProtocolEdit):
    replacement = protocol_content(body.protocol)
    with store.connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT kind,content FROM artifacts WHERE id=?", (identifier,)
        ).fetchone()
        if not row:
            raise KeyError(identifier)
        if row["kind"] != "protocol":
            raise ValueError("请选择实验设计卡")
        old = json.loads(row["content"])
        if old["revision"] != body.revision:
            raise HTTPException(409, "设计卡已更新，请重新打开后修改")
        history = old.get("history", []) + [
            {"revision": old["revision"], "protocol": old["protocol"]}
        ]
        content = {**replacement, "revision": body.revision + 1, "history": history}
        conn.execute(
            "UPDATE artifacts SET title=?,content=? WHERE id=?",
            (body.protocol.title, json.dumps(content, ensure_ascii=False), identifier),
        )
    return {"id": identifier, "kind": "protocol", **content}


class PreflightRequest(BaseModel):
    revision: int = Field(ge=1)


@router.post("/protocols/{identifier}/preflight")
def check_execution(identifier: str, body: PreflightRequest):
    item = research.artifact(identifier)
    if item["kind"] != "protocol":
        raise ValueError("请选择实验设计卡")
    content = item["content"]
    if body.revision != content["revision"]:
        raise HTTPException(409, "设计卡已更新，请重新打开并保存后预检")
    protocol = content["protocol"]
    if not protocol.get("execution"):
        raise ValueError("请先填写并保存结构化执行参数")
    result = preflight(protocol["execution"], protocol["seeds"][0])
    return research.save_artifact(
        "preflight",
        "执行预检 · " + item["title"],
        {
            **result,
            "protocol_snapshot": {
                "id": identifier,
                "revision": content["revision"],
                "protocol": protocol,
            },
        },
    )


class Measurements(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    csv: str = Field(min_length=1, max_length=2_000_000)
    group: str = Field(min_length=1, max_length=100)
    run: str = Field(min_length=1, max_length=100)
    metric: str = Field(min_length=1, max_length=100)
    unit: str = Field(default="", max_length=100)
    interval: Literal["sd", "ci95"] = "sd"
    protocol_id: str | None = None
    protocol_revision: int | None = Field(default=None, ge=1)
    data_label: Literal["measured", "example"] = "measured"


def summarize(spec):
    """A row is one independent run, not a batch, epoch or individual prediction."""
    headers, rows = charts.parse_csv(spec["csv"])
    columns = [spec[k] for k in ["group", "run", "metric"]]
    if len(set(columns)) != 3 or any(k not in headers for k in columns):
        raise ValueError("请选择三个不同且存在的列：方法、独立运行标识、数值指标")
    grouped, seen = {}, set()
    # Keep physical CSV source lines even when parsing skips blank records or a
    # quoted field spans multiple lines.
    reader = csv.reader(io.StringIO(spec["csv"].lstrip("\ufeff")))
    next(reader)
    source_lines = []
    while True:
        start = reader.line_num + 1
        try:
            record = next(reader)
        except StopIteration:
            break
        if any(value.strip() for value in record):
            source_lines.append(start)
    for line, row in zip(source_lines, rows):
        group, run, raw = [row[k] for k in columns]
        if not group or not run or not raw:
            raise ValueError(
                f"第 {line} 行缺少方法、运行标识或指标；不会静默丢弃失败运行"
            )
        if len(group) > 150 or len(run) > 150:
            raise ValueError("方法名和运行标识最多 150 字")
        if (group, run) in seen:
            raise ValueError(
                f"第 {line} 行重复了同一方法的运行标识，不能当作独立重复计数"
            )
        seen.add((group, run))
        try:
            value = float(raw)
        except ValueError:
            raise ValueError(f"第 {line} 行的指标不是数字") from None
        if not math.isfinite(value) or abs(value) > 1e100:
            raise ValueError(f"第 {line} 行指标不是有限的可计算数值")
        grouped.setdefault(group, []).append(
            {"run": run, "value": value, "csv_line": line}
        )
    if not 1 <= len(grouped) <= 30:
        raise ValueError("需要 1—30 个方法组")
    summary = []
    for group, runs in grouped.items():
        if len(runs) < 2:
            raise ValueError(
                f"方法 {group} 仅有一次运行，无法计算样本波动；至少提供两次独立运行"
            )
        values = np.asarray([r["value"] for r in runs], dtype=float)
        n = len(values)
        mean, sd = float(values.mean()), float(values.std(ddof=1))
        half = float(t.ppf(0.975, n - 1)) * sd / math.sqrt(n)
        summary.append(
            {
                "group": group,
                "n": n,
                "mean": mean,
                "sd": sd,
                "ci95_low": mean - half,
                "ci95_high": mean + half,
                "error": sd if spec["interval"] == "sd" else half,
                "runs": runs,
            }
        )
    warnings = [
        "每行必须是独立实验运行；同一次训练的不同 batch、epoch 或预测样本不能作为独立种子。",
        "误差棒重叠或不重叠都不能单独证明统计显著性；本结果不进行因果推断或自动胜负排名。",
    ]
    if spec["interval"] == "ci95":
        warnings.append(
            "95% 区间使用 Student t 均值置信区间，假设运行独立且均值推断适用；小样本或偏态时可能不可靠，也不是未来单次运行的范围。"
        )
    if any(row["n"] < 5 for row in summary):
        warnings.append("部分方法少于 5 次运行，波动估计不稳定；请结合原始测量复核。")
    if len({tuple(sorted(r["run"] for r in row["runs"])) for row in summary}) > 1:
        warnings.append("各方法的运行标识集合不一致，不能把这些结果自动当作成对比较。")
    if spec["data_label"] == "example":
        warnings.insert(0, "这是示例数据，不是论文实验结果。")
    return {
        "summary": summary,
        "warnings": warnings,
        "source_sha256": hashlib.sha256(spec["csv"].encode("utf-8")).hexdigest(),
        "method": "sample SD (ddof=1); two-sided Student t mean interval at 95%",
        "notice": "统计仅基于提供的 CSV，未验证测量真实性；原始数据、行号、设计卡修订和计算设置均保留。",
    }


def render_measurements(spec, result, folder):
    import matplotlib.pyplot as plt

    folder.mkdir(parents=True, exist_ok=True)
    with charts.plot_lock:
        plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False
        fig, ax = plt.subplots(figsize=(10, 6), layout="constrained")
        rows = result["summary"]
        xs = np.arange(len(rows))
        ax.errorbar(
            xs,
            [r["mean"] for r in rows],
            yerr=[r["error"] for r in rows],
            fmt="o",
            capsize=5,
            color="#246454",
            label="Mean ± " + ("sample SD" if spec["interval"] == "sd" else "95% t CI"),
        )
        for x, row in zip(xs, rows):
            offsets = np.linspace(-0.12, 0.12, row["n"])
            ax.scatter(
                x + offsets,
                [r["value"] for r in row["runs"]],
                alpha=0.5,
                s=14,
                color="#d28b40",
            )
        ax.set_xticks(
            xs, [f"{r['group']} (n={r['n']})" for r in rows], rotation=20, ha="right"
        )
        ax.set_ylabel(spec["metric"] + (f" ({spec['unit']})" if spec["unit"] else ""))
        ax.set_title(
            spec["title"] + (" · 示例数据" if spec["data_label"] == "example" else "")
        )
        ax.grid(axis="y", alpha=0.2)
        ax.legend()
        try:
            for ext in ["png", "svg", "pdf"]:
                fig.savefig(folder / f"chart.{ext}", dpi=160)
        finally:
            plt.close(fig)


def write_bundle(spec, result, folder):
    render_measurements(spec, result, folder)
    (folder / "raw.csv").write_bytes(spec["csv"].encode("utf-8"))
    (folder / "spec.json").write_text(
        json.dumps(
            {k: v for k, v in spec.items() if k != "csv"}, ensure_ascii=False, indent=2
        ),
        encoding="utf-8",
    )
    (folder / "analysis.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["method", "n", "mean", "sample_sd", "ci95_low", "ci95_high"])
    for row in result["summary"]:
        label = row["group"]
        if label.startswith(("=", "+", "-", "@")):
            label = "'" + label
        writer.writerow(
            [label] + [row[k] for k in ["n", "mean", "sd", "ci95_low", "ci95_high"]]
        )
    (folder / "summary.csv").write_text(buffer.getvalue(), encoding="utf-8-sig")
    (folder / "reproduce.py").write_text(
        'from pathlib import Path\nimport json, sys\nsys.path.insert(0, str(Path.cwd()))\nfrom backend.experiments import summarize, render_measurements\np=Path(__file__).resolve().parent\nspec=json.loads((p/"spec.json").read_text(encoding="utf-8"))\nspec["csv"]=(p/"raw.csv").read_bytes().decode("utf-8")\nresult=summarize(spec)\nrender_measurements(spec,result,p/"rerun")\n(p/"rerun"/"analysis.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")\nprint(result["source_sha256"])\n',
        encoding="utf-8",
    )
    (folder / "README.txt").write_text(
        "从 Moheng 项目根目录运行：\n.venv/Scripts/python.exe <解压目录>/reproduce.py\n须从包含 backend 文件夹的项目根目录运行。需要项目依赖 numpy/scipy/matplotlib。\nraw.csv 保留原始输入，summary.csv 为统计汇总；原始 CSV 可能包含用户文本，请按文本数据导入。\nCI 不是显著性检验。未运行模型训练或验证原数据真实性。\n",
        encoding="utf-8",
    )


@router.post("/analyze")
def analyze(body: Measurements):
    spec = body.model_dump()
    result = summarize(spec)
    if body.protocol_revision and not body.protocol_id:
        raise ValueError("选择实验设计版本时必须指定设计卡")
    if body.protocol_id:
        protocol = research.artifact(body.protocol_id)
        if protocol["kind"] != "protocol":
            raise ValueError("关联对象必须是实验设计卡")
        saved = protocol["content"]
        selected_revision = body.protocol_revision or saved["revision"]
        selected = (
            saved["protocol"]
            if selected_revision == saved["revision"]
            else next(
                (
                    h["protocol"]
                    for h in saved.get("history", [])
                    if h["revision"] == selected_revision
                ),
                None,
            )
        )
        if selected is None:
            raise HTTPException(409, "所选实验设计版本不存在，请重新选择")
        result["protocol_snapshot"] = {
            "id": body.protocol_id,
            "revision": selected_revision,
            "protocol": selected,
        }
        if body.protocol_revision is None:
            result["warnings"].append(
                "未显式选择设计版本，本次使用保存统计时的最新版；核对是否与实际实验一致。"
            )
        if selected_revision != saved["revision"]:
            result["warnings"].append(
                f"本次使用历史设计第 {selected_revision} 版，当前最新版为第 {saved['revision']} 版；结果按所选历史条件保存。"
            )
        if body.metric.casefold() != selected["metric"].casefold():
            result["warnings"].append(
                "CSV 指标列名与设计卡指标名称不同，请核对含义和单位。"
            )
        expected = {str(seed) for seed in selected["seeds"]}
        if any(
            {r["run"] for r in row["runs"]} != expected for row in result["summary"]
        ):
            result["warnings"].append(
                "实测运行标识与设计卡种子集合不一致，核对缺失、失败或额外运行，并报告偏离计划的原因。"
            )
    # Render before saving a visible artifact, so a plotting failure leaves no false success.
    import uuid

    identifier = uuid.uuid4().hex
    folder = store.database_path().parent / "experiments" / identifier
    write_bundle(spec, result, folder)
    content = {**result, "spec": spec}
    with store.connection() as conn:
        conn.execute(
            "INSERT INTO artifacts(id,kind,title,content) VALUES(?,?,?,?)",
            (
                identifier,
                "measurements",
                body.title,
                json.dumps(content, ensure_ascii=False),
            ),
        )
    return {"id": identifier, "kind": "measurements", "title": body.title, **content}


FILES = {
    "chart.png",
    "chart.svg",
    "chart.pdf",
    "raw.csv",
    "summary.csv",
    "spec.json",
    "analysis.json",
    "reproduce.py",
    "README.txt",
}


@router.get("/{identifier}/files/{filename}")
def file(identifier: str, filename: str):
    item = research.artifact(identifier)
    if item["kind"] != "measurements":
        raise ValueError("请选择重复实验统计成果")
    folder = store.database_path().parent / "experiments" / identifier
    if filename == "bundle.zip":
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for name in sorted(FILES):
                archive.write(folder / name, name)
        return Response(
            buffer.getvalue(),
            media_type="application/zip",
            headers={
                "Content-Disposition": 'attachment; filename="experiment-reproduction.zip"'
            },
        )
    if filename not in FILES:
        raise KeyError(filename)
    return FileResponse(
        folder / filename,
        filename=filename,
        content_disposition_type="inline"
        if filename.endswith(".png")
        else "attachment",
    )
