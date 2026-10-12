"""CSV analysis using fixed plotting templates; never execute model-generated code."""

import csv
import io
import json
import math
import re
import threading

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from . import research, store

plot_lock = threading.Lock()
COLORS = ["#246454", "#d28b40", "#487caf", "#a15c85", "#70874c", "#aa614f"]


def parse_csv(text):
    if len(text.encode("utf-8")) > 2_000_000:
        raise ValueError("CSV 上限 2 MB")
    rows = list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))
    if len(rows) < 2:
        raise ValueError("CSV 至少需要表头和一行数据")
    headers = [h.strip() for h in rows[0]]
    if not all(headers) or len(headers) != len(set(headers)):
        raise ValueError("列名不能为空或重复")
    if len(headers) > 40 or len(rows) > 10001:
        raise ValueError("最多 40 列、10000 行")
    data = []
    for index, row in enumerate(rows[1:], 2):
        if not any(v.strip() for v in row):
            continue
        if len(row) != len(headers):
            raise ValueError(f"第 {index} 行列数与表头不一致")
        data.append(dict(zip(headers, [v.strip() for v in row])))
    return headers, data


def prepare(spec):
    headers, rows = parse_csv(spec["csv"])
    x = spec["x"]
    ys = spec["ys"]
    kind = spec["kind"]
    if x not in headers or not ys or any(y not in headers for y in ys):
        raise ValueError("请选择存在的横轴列和数值列")
    if len(ys) > 6 or len(ys) != len(set(ys)):
        raise ValueError("最多选择 6 个不同数值列")
    if kind not in {"line", "bar", "table", "radar3d", "scatter"}:
        raise ValueError("不支持的图表类型")
    if kind == "radar3d" and not 3 <= len(ys) <= 6:
        raise ValueError("三维雷达需要 3—6 个指标列")
    labels = []
    values = []
    missing = 0
    for index, row in enumerate(rows, 2):
        if any(row[y] == "" or row[y].lower() in {"nan", "na", "null"} for y in ys):
            missing += 1
            continue
        try:
            v = [float(row[y]) for y in ys]
        except ValueError:
            raise ValueError(f"第 {index} 行的数值列包含非数字") from None
        if not all(math.isfinite(n) for n in v):
            raise ValueError("数据不能包含无穷大或 NaN")
        labels.append(row[x])
        values.append(v)
    if not values:
        raise ValueError("没有完整的数值行可绘图")
    for scale in [spec.get("xscale", "linear"), spec.get("yscale", "linear")]:
        if scale not in {"linear", "log"}:
            raise ValueError("刻度须为 linear 或 log")
    if kind in {"table", "radar3d"} and spec.get("yscale", "linear") != "linear":
        raise ValueError("表格和归一化雷达图不使用对数刻度")
    if spec.get("yscale") == "log" and any(n <= 0 for row in values for n in row):
        raise ValueError("对数纵轴要求所有数值大于 0；请修改刻度或核对数据")
    if kind == "scatter" or spec.get("xscale") == "log":
        try:
            numbers = [float(label) for label in labels]
        except ValueError:
            raise ValueError("散点图或对数横轴需要数值横轴") from None
        if (
            not all(math.isfinite(n) for n in numbers)
            or spec.get("xscale") == "log"
            and any(n <= 0 for n in numbers)
        ):
            raise ValueError("横轴数值无效；对数刻度要求所有值大于 0")
    if kind in {"bar", "table", "radar3d"} and spec.get("xscale", "linear") != "linear":
        raise ValueError("分类图表不使用对数横轴")
    if kind in {"bar", "table", "radar3d"} and len(values) > 40:
        raise ValueError("柱状、表格、雷达最多 40 行，请先筛选 CSV")
    return labels, np.asarray(values), missing


def render(spec, folder):
    labels, values, missing = prepare(spec)
    ys = spec["ys"]
    kind = spec["kind"]
    with plot_lock:
        plt.rcParams["font.sans-serif"] = [
            "Microsoft YaHei",
            "SimHei",
            "Noto Sans CJK SC",
            "DejaVu Sans",
        ]
        plt.rcParams["axes.unicode_minus"] = False
        fig = plt.figure(figsize=(10, 6), layout="constrained")
        ax = fig.add_subplot(111, projection="3d" if kind == "radar3d" else None)
        if kind == "table":
            ax.axis("off")
            ax.table(
                cellText=[
                    [label] + [f"{n:g}" for n in row]
                    for label, row in zip(labels, values)
                ],
                colLabels=[spec["x"]] + ys,
                loc="center",
            )
        elif kind == "radar3d":
            angles = np.linspace(0, 2 * np.pi, len(ys), endpoint=False)
            low = values.min(axis=0)
            span = values.max(axis=0) - low
            normalized = np.divide(
                values - low, span, out=np.full_like(values, 0.5), where=span != 0
            )
            for i, row in enumerate(normalized):
                radial = np.r_[row, row[0]]
                theta = np.r_[angles, angles[0]]
                ax.plot(
                    radial * np.cos(theta),
                    radial * np.sin(theta),
                    np.full(len(theta), i),
                    color=COLORS[i % 6],
                    label=labels[i],
                )
            for angle, name in zip(angles, ys):
                ax.text(np.cos(angle) * 1.12, np.sin(angle) * 1.12, 0, name)
            ax.set_zlabel(spec["x"] + " (row index)")
            ax.set_title(
                spec.get("title", "") + "\nMin-max by metric; constant metrics = 0.5"
            )
        else:
            indices = np.arange(len(labels))
            if kind in {"line", "scatter"}:
                try:
                    numeric_x = np.asarray([float(label) for label in labels])
                    if not np.all(np.isfinite(numeric_x)):
                        raise ValueError("数值横轴不能包含无穷大或 NaN")
                    order = np.argsort(numeric_x, kind="stable")
                    indices, values = numeric_x[order], values[order]
                    labels = [labels[i] for i in order]
                except ValueError:
                    if all(re.fullmatch(r"[\d.eE+\-]+", label) for label in labels):
                        raise
            for i, name in enumerate(ys):
                if kind == "line":
                    ax.plot(
                        indices,
                        values[:, i],
                        label=name,
                        color=COLORS[i % 6],
                        marker="o" if len(labels) < 40 else None,
                        markersize=3,
                    )
                elif kind == "scatter":
                    ax.scatter(
                        indices,
                        values[:, i],
                        label=name,
                        color=COLORS[i % 6],
                        s=24,
                        alpha=0.85,
                    )
                else:
                    ax.bar(
                        indices + (i - (len(ys) - 1) / 2) * 0.8 / len(ys),
                        values[:, i],
                        width=0.8 / len(ys),
                        label=name,
                        color=COLORS[i % 6],
                    )
            step = max(1, len(labels) // 20)
            ax.set_xticks(indices[::step], labels[::step], rotation=30, ha="right")
            ax.set_xscale(spec.get("xscale", "linear"))
            ax.set_yscale(spec.get("yscale", "linear"))
            ax.set_xlabel(spec["x"])
            ax.set_ylabel(spec.get("unit", "Value"))
            ax.grid(axis="y", alpha=0.2)
            ax.legend()
            ax.set_title(spec.get("title", ""))
        folder.mkdir(parents=True, exist_ok=True)
        try:
            for extension in ["png", "svg", "pdf"]:
                fig.savefig(folder / ("chart." + extension), dpi=180)
        finally:
            plt.close(fig)
    stats = [
        {
            "column": name,
            "min": float(values[:, i].min()),
            "max": float(values[:, i].max()),
            "mean": float(values[:, i].mean()),
            "first": float(values[0, i]),
            "last": float(values[-1, i]),
        }
        for i, name in enumerate(ys)
    ]
    caption = (
        f"图展示 {len(values)} 行数据，横轴为 {spec['x']}；跳过 {missing} 行缺失值。"
        + "".join(
            f"{s['column']} 范围为 {s['min']:g}—{s['max']:g}，均值 {s['mean']:.4g}。"
            for s in stats
        )
    )
    if kind == "radar3d":
        caption += "各指标分别进行 min-max 归一化，常量列置为 0.5；高度表示数据行序号，不代表额外测量维度。"
    caption += "此描述不包含统计显著性或因果推断。"
    return {
        "stats": stats,
        "caption": caption,
        "rows": len(values),
        "missing_rows": missing,
        "normalization": "min-max per metric" if kind == "radar3d" else None,
    }


def create(spec):
    # Validate before creating an artifact, and keep account-local output locations.
    prepare(spec)
    item = research.save_artifact(
        "chart", spec.get("title") or "CSV 图表", {"spec": spec}
    )
    folder = store.database_path().parent / "exports" / item["id"]
    result = render(spec, folder)
    (folder / "data.csv").write_text(spec["csv"], encoding="utf-8-sig")
    (folder / "spec.json").write_text(
        json.dumps(
            {k: v for k, v in spec.items() if k != "csv"}, ensure_ascii=False, indent=2
        ),
        encoding="utf-8",
    )
    # Reproducible entrypoint calls the same fixed renderer in the submitted project.
    (folder / "reproduce.py").write_text(
        'from pathlib import Path\nimport json\nfrom backend.charts import render\np = Path(__file__).resolve().parent\nspec = json.loads((p / "spec.json").read_text(encoding="utf-8"))\nspec["csv"] = (p / "data.csv").read_text(encoding="utf-8-sig")\nprint(render(spec, p / "rerun"))\n',
        encoding="utf-8",
    )
    content = {"spec": spec, **result}
    with store.connection() as conn:
        conn.execute(
            "UPDATE artifacts SET content=? WHERE id=?",
            (json.dumps(content, ensure_ascii=False), item["id"]),
        )
    return {"id": item["id"], "kind": "chart", **content}
