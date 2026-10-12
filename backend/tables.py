"""Extract editable table candidates from source geometry, without generating cell values."""

import asyncio
import csv
import io
import json
import math
import os
import re
import statistics
import subprocess
import sys
import time
from itertools import pairwise

import cv2
import numpy as np
import pymupdf

from . import jobs, research, store

gate = asyncio.Semaphore(1)


def area_for(record, number, bounds):
    if not 1 <= number <= record["pages"]:
        raise ValueError("表格页码超出范围")
    if (
        not isinstance(bounds, list)
        or len(bounds) != 4
        or not all(math.isfinite(v) for v in bounds)
    ):
        raise ValueError("请框选有效的表格区域")
    with pymupdf.open(record["path"]) as pdf:
        page = pdf[number - 1]
        area = pymupdf.Rect(bounds) & page.rect
        if area.width < 30 or area.height < 15 or area.width * area.height > 600000:
            raise ValueError("请完整框选一张表格")
        return area, page.rect.width, page.rect.height


def regions(identifier, number):
    record = store.get_document(identifier)
    if not 1 <= number <= record["pages"]:
        raise ValueError("页码超出范围")
    with pymupdf.open(record["path"]) as pdf:
        page = pdf[number - 1]
        pix = page.get_pixmap(dpi=110, alpha=False)
        pixels = np.frombuffer(pix.samples, np.uint8).reshape(
            pix.height, pix.width, pix.n
        )
        gray = cv2.cvtColor(pixels, cv2.COLOR_RGB2GRAY)
        binary = cv2.threshold(gray, 190, 255, cv2.THRESH_BINARY_INV)[1]
        horizontal = cv2.morphologyEx(
            binary, cv2.MORPH_OPEN, np.ones((1, max(70, pix.width // 5)), np.uint8)
        )
        contours, _ = cv2.findContours(
            horizontal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        lines = sorted([cv2.boundingRect(c) for c in contours], key=lambda r: r[1])
        families = []
        for x, y, w, h in lines:
            family = next(
                (
                    f
                    for f in families
                    if abs(f[-1][0] - x) < 15
                    and abs(f[-1][2] - w) < 20
                    and y - f[-1][1] < pix.height * 0.3
                ),
                None,
            )
            if family is None:
                family = []
                families.append(family)
            family.append((x, y, w, h))
        found = []
        for family in families:
            if len(family) < 3 or family[-1][1] - family[0][1] < 25:
                continue
            x0 = max(0, min(f[0] for f in family) - 3)
            x1 = min(pix.width, max(f[0] + f[2] for f in family) + 3)
            y0, y1 = (
                max(0, family[0][1] - 3),
                min(pix.height, family[-1][1] + family[-1][3] + 3),
            )
            found.append(
                {
                    "page": number,
                    "document_id": identifier,
                    "width": page.rect.width,
                    "height": page.rect.height,
                    "bbox": [
                        x0 * page.rect.width / pix.width,
                        y0 * page.rect.height / pix.height,
                        x1 * page.rect.width / pix.width,
                        y1 * page.rect.height / pix.height,
                    ],
                }
            )
        found.sort(key=lambda r: r["bbox"][1])
        return {
            "regions": found[:12],
            "width": page.rect.width,
            "height": page.rect.height,
        }


def line_groups(tokens):
    if not tokens:
        return []
    height = statistics.median(t["bbox"][3] - t["bbox"][1] for t in tokens)
    groups = []
    for token in sorted(
        tokens, key=lambda t: ((t["bbox"][1] + t["bbox"][3]) / 2, t["bbox"][0])
    ):
        cy = (token["bbox"][1] + token["bbox"][3]) / 2
        if (
            not groups
            or abs(
                cy
                - statistics.median(
                    (t["bbox"][1] + t["bbox"][3]) / 2 for t in groups[-1]
                )
            )
            > height * 0.55
        ):
            groups.append([])
        groups[-1].append(token)
    return [sorted(row, key=lambda t: t["bbox"][0]) for row in groups]


def native_tokens(page, area):
    words = [
        {"text": w[4], "bbox": list(w[:4]), "confidence": None}
        for w in page.get_text("words")
        if (pymupdf.Rect(w[:4]) & area).get_area()
        >= pymupdf.Rect(w[:4]).get_area() * 0.85
    ]
    tokens = []
    for row in line_groups(words):
        current = None
        for word in row:
            if current and word["bbox"][0] - current["bbox"][2] < 5:
                current["text"] += " " + word["text"]
                current["bbox"] = list(
                    pymupdf.Rect(current["bbox"]) | pymupdf.Rect(word["bbox"])
                )
            else:
                current = {**word, "bbox": list(word["bbox"])}
                tokens.append(current)
    return tokens


def grid_from_tokens(tokens, area, column_bounds=None):
    rows = line_groups(tokens)
    if len(rows) < 2 or len(tokens) > 2500:
        raise ValueError("没有识别到可用表格，请调整框选范围")
    x0, y0, x1, y1 = area
    if column_bounds is None:
        # Repeated whitespace gutters indicate columns; a spanning heading may cross them.
        counts = np.zeros(math.ceil((x1 - x0) * 2) + 1, dtype=np.int32)
        for row in rows:
            occupied = np.zeros_like(counts)
            for token in row:
                a = max(0, math.floor((token["bbox"][0] - x0) * 2))
                b = min(len(counts), math.ceil((token["bbox"][2] - x0) * 2))
                occupied[a:b] = 1
            counts += occupied
        gaps = []
        start = None
        left_peak = np.zeros_like(counts)
        right_peak = np.zeros_like(counts)
        for offset in range(1, min(81, len(counts))):
            left_peak[offset:] = np.maximum(left_peak[offset:], counts[:-offset])
            right_peak[:-offset] = np.maximum(right_peak[:-offset], counts[offset:])
        limits = np.minimum(3, np.minimum(left_peak, right_peak) * 0.45)
        for i, value in enumerate([*counts, len(rows)]):
            limit = limits[i] if i < len(counts) else -1
            if value <= limit and start is None:
                start = i
            elif value > limit and start is not None:
                if start > 0 and i < len(counts) and i - start >= 6:
                    gaps.append(x0 + (start + i) / 4)
                start = None
        column_bounds = gaps
    if (
        len(column_bounds) > 31
        or any(not math.isfinite(x) or not x0 < x < x1 for x in column_bounds)
        or column_bounds != sorted(set(column_bounds))
    ):
        raise ValueError("分列线需按从左到右顺序设置在表格内，最多 31 条")
    edges = [x0, *column_bounds, x1]
    centers = [
        statistics.median((t["bbox"][1] + t["bbox"][3]) / 2 for t in row)
        for row in rows
    ]
    ys = [y0, *[(a + b) / 2 for a, b in pairwise(centers)], y1]
    cells, values = [], []
    for r, row in enumerate(rows):
        cell_row, value_row = [], []
        for c, (left, right) in enumerate(pairwise(edges)):
            selected = [
                t for t in row if left <= (t["bbox"][0] + t["bbox"][2]) / 2 < right
            ]
            values_with_spans = []
            for token in selected:
                crossed = [
                    index + 1
                    for index, (a, b) in enumerate(pairwise(edges))
                    if min(token["bbox"][2], b) - max(token["bbox"][0], a) > 2
                ]
                prefix = (
                    f"[跨列 {crossed[0]}-{crossed[-1]}] " if len(crossed) > 1 else ""
                )
                values_with_spans.append(prefix + token["text"])
            value = " ".join(values_with_spans)
            scores = [t["confidence"] for t in selected if t["confidence"] is not None]
            crossing = any(
                t["bbox"][0] < left - 2 or t["bbox"][2] > right + 2 for t in selected
            )
            cell_row.append(
                {
                    "text": value,
                    "bbox": [left, ys[r], right, ys[r + 1]],
                    "confidence": min(scores) if scores else None,
                    "spans_columns": crossing,
                    "tokens": selected,
                }
            )
            value_row.append(value)
        cells.append(cell_row)
        values.append(value_row)
    if len(values) > 200:
        raise ValueError("单次最多识别 200 行，请分段框选")
    return {"rows": values, "cells": cells, "column_bounds": column_bounds}


def validate_rows(rows):
    if not rows or len(rows) > 200 or not rows[0] or len(rows[0]) > 32:
        raise ValueError("表格须为 1—200 行、1—32 列")
    if any(len(row) != len(rows[0]) for row in rows) or any(
        not isinstance(v, str) or len(v) > 2000 for row in rows for v in row
    ):
        raise ValueError("请保持各行列数一致，单元格最多 2000 字")
    return rows


def csv_text(rows):
    validate_rows(rows)
    buffer = io.StringIO(newline="")
    # Prevent a paper's text from becoming an executable spreadsheet formula.
    csv.writer(buffer).writerows(
        [
            [
                "'" + cell
                if cell.lstrip().startswith(("=", "+", "@"))
                or (
                    cell.lstrip().startswith("-")
                    and not re.fullmatch(r"\s*-\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\s*", cell)
                )
                or cell.startswith(("\t", "\r", "\n"))
                else cell
                for cell in row
            ]
            for row in rows
        ]
    )
    return "\ufeff" + buffer.getvalue()


@jobs.register("table")
async def extract(ctx, payload):
    record = store.get_document(payload["document_id"])
    number = payload.get("page", 1)
    area, width, height = area_for(record, number, payload.get("bbox", []))
    start = time.monotonic()
    ctx.progress(0.1, "检查所选表格的原始文字与坐标")
    with pymupdf.open(record["path"]) as pdf:
        tokens = native_tokens(pdf[number - 1], area)
        folder = store.database_path().parent / "exports" / ("table-" + ctx.id)
        folder.mkdir(parents=True, exist_ok=True)
        crop = folder / "source.png"
        pix = pdf[number - 1].get_pixmap(dpi=220, clip=area, alpha=False)
        pix.save(crop)
        # Pixmap origins are rounded to device pixels. Keep the exact source mapping.
        origin = (pix.x / (220 / 72), pix.y / (220 / 72))
    method = "PDF word geometry"
    if len(tokens) < 4:
        method = "RapidOCR / ONNX CPU + spatial grid"
        async with gate:
            ctx.check()
            ctx.progress(0.3, "本地识别扫描表格，保留每个文字框")
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-X",
                "utf8",
                str(store.ROOT / "scripts/table_worker.py"),
                str(crop),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                **(
                    {"creationflags": subprocess.CREATE_NO_WINDOW}
                    if os.name == "nt"
                    else {}
                ),
            )
            try:
                stdout, _ = await asyncio.wait_for(process.communicate(), timeout=90)
                ctx.check()
                if process.returncode:
                    raise ValueError("扫描识别失败，请调整区域后重试")
                tokens = json.loads(stdout.decode("utf-8").strip().splitlines()[-1])
                for token in tokens:
                    token["bbox"] = [
                        v / (220 / 72) + origin[i % 2]
                        for i, v in enumerate(token["bbox"])
                    ]
            finally:
                if process.returncode is None:
                    process.kill()
                    await process.communicate()
    ctx.progress(0.8, "按文字位置分行分列，保留空白单元格")
    grid = grid_from_tokens(tokens, list(area))
    return research.save_artifact(
        "table",
        f"{record['title']} · 第 {number} 页表格",
        {
            **grid,
            "original_rows": grid["rows"],
            "original_cells": grid["cells"],
            "tokens": tokens,
            "source": {
                "document_id": record["id"],
                "page": number,
                "bbox": list(area),
                "width": width,
                "height": height,
            },
            "method": method,
            "seconds": round(time.monotonic() - start, 2),
            "revision": 0,
            "notice": "自动提取候选。空白不补值；[跨列] 标记表示合并内容，不属于单独一列。幂次、上下标和 OCR 错字需对照原图；点击单元格可定位，修改与重新分列保留历史。",
        },
    )
