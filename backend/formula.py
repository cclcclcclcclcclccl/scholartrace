"""Source-cropped formula OCR in a separate, bounded CPU process."""

import asyncio
import json
import math
import os
import re
import subprocess
import pymupdf
from . import store, jobs, research

ROOT = store.ROOT
PYTHON = (
    ROOT
    / "tools/formula-env"
    / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
)
gate = asyncio.Semaphore(1)


def available():
    return PYTHON.is_file() and all(
        (ROOT / "models/formula" / n).is_file()
        for n in [
            "encoder.onnx",
            "decoder.onnx",
            "image_resizer.onnx",
            "tokenizer.json",
        ]
    )


def area_for(record, number, bounds):
    if not 1 <= number <= record["pages"]:
        raise ValueError("公式页码超出范围")
    if (
        not isinstance(bounds, list)
        or len(bounds) != 4
        or not all(math.isfinite(v) for v in bounds)
    ):
        raise ValueError("请框选有效的公式区域")
    with pymupdf.open(record["path"]) as pdf:
        page = pdf[number - 1]
        area = pymupdf.Rect(bounds) & page.rect
        if area.width < 4 or area.height < 4 or area.width * area.height > 110000:
            raise ValueError("请单独框选一条公式，不要选择整页")
        return area, page.rect.width, page.rect.height


def regions(identifier, number):
    record = store.get_document(identifier)
    if not 1 <= number <= record["pages"]:
        raise ValueError("页码超出范围")
    result = []
    with pymupdf.open(record["path"]) as pdf:
        page = pdf[number - 1]
        blocks = []
        for block in page.get_text("dict")["blocks"]:
            spans = [
                s
                for line in block.get("lines", [])
                for s in line["spans"]
                if not re.fullmatch(r"\s*\(\d+\)\s*", s["text"])
            ]
            if not spans:
                continue
            rect = pymupdf.Rect(spans[0]["bbox"])
            for span in spans[1:]:
                rect |= pymupdf.Rect(span["bbox"])
            text = " ".join(s["text"] for s in spans)
            blocks.append((rect, text))
        for rect, text in blocks:
            if (
                "=" not in text
                or len(re.findall(r"[A-Za-z]{3,}", text)) > 12
                or rect.height > 45
                or rect.x0 < page.rect.width * 0.23
            ):
                continue
            bounds = pymupdf.Rect(rect)
            window = pymupdf.Rect(rect.x0 - 15, rect.y0 - 6, rect.x1 + 60, rect.y1 + 16)
            for other, words in blocks:
                if len(words) < 120 and other.intersects(window) and other.height < 32:
                    bounds |= other
            bounds = (bounds + (-4, -4, 4, 4)) & page.rect
            if not any(pymupdf.Rect(r["bbox"]).intersects(bounds) for r in result):
                result.append(
                    {
                        "bbox": list(bounds),
                        "text": text,
                        "page": number,
                        "document_id": identifier,
                        "width": page.rect.width,
                        "height": page.rect.height,
                    }
                )
        return {
            "regions": result,
            "width": page.rect.width,
            "height": page.rect.height,
            "available": available(),
        }


def validation(latex):
    if not isinstance(latex, str) or not latex.strip() or len(latex) > 12000:
        raise ValueError("模型未给出有效公式，请重新框选")
    warnings = []
    for opening, closing in [("{", "}"), ("(", ")"), ("[", "]")]:
        if latex.count(opening) != latex.count(closing):
            warnings.append("括号可能未配对，请对照原图修改")
            break
    return warnings


@jobs.register("formula")
async def recognize(ctx, payload):
    if not available():
        raise ValueError("尚未安装本地公式组件，请运行 scripts/install_formula.py")
    record = store.get_document(payload["document_id"])
    number = payload.get("page", 1)
    area, width, height = area_for(record, number, payload.get("bbox", []))
    folder = store.database_path().parent / "exports" / ("formula-" + ctx.id)
    folder.mkdir(parents=True, exist_ok=True)
    crop = folder / "source.png"
    with pymupdf.open(record["path"]) as pdf:
        pdf[number - 1].get_pixmap(dpi=220, clip=area, alpha=False).save(crop)
    ctx.progress(0.1, "原图已裁剪，等待本地公式识别")
    async with gate:
        ctx.check()
        ctx.progress(0.3, "离线识别公式，保留符号与上下标")
        process = await asyncio.create_subprocess_exec(
            str(PYTHON),
            "-X",
            "utf8",
            str(ROOT / "scripts/formula_worker.py"),
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
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
            ctx.check()
            if process.returncode != 0:
                raise ValueError("公式识别失败，请缩小框选区域后重试")
            value = json.loads(stdout.decode("utf-8").strip().splitlines()[-1])
            warnings = validation(value["latex"])
        finally:
            if process.returncode is None:
                process.kill()
                await process.communicate()
    return research.save_artifact(
        "formula",
        f"{record['title']} · 第 {number} 页公式",
        {
            "latex": value["latex"],
            "original_ocr": value["latex"],
            "warnings": warnings,
            "source": {
                "document_id": record["id"],
                "page": number,
                "bbox": list(area),
                "width": width,
                "height": height,
            },
            "engine": "RapidLaTeXOCR 0.0.9 / ONNX CPU",
            "seconds": value["seconds"],
            "notice": "公式识别候选，未自动判定正确。请逐项核对上下标、括号和符号；原图始终保留，可修改后导出。",
        },
    )
