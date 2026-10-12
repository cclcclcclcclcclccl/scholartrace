"""Run bounded local table OCR; print only measured text, boxes and confidence."""

import json
import sys
from pathlib import Path

import numpy as np
from rapidocr import RapidOCR

path = Path(sys.argv[1]).resolve(strict=True)
if path.suffix != ".png" or not path.parent.name.startswith("table-"):
    raise SystemExit("Expected a table source crop")
engine = RapidOCR(
    params={
        "Global.text_score": 0.45,
        "EngineConfig.onnxruntime.intra_op_num_threads": 2,
        "EngineConfig.onnxruntime.inter_op_num_threads": 2,
    }
)
output = engine(str(path))
items = []
if output.boxes is not None:
    for text, box, score in zip(output.txts, output.boxes, output.scores):
        xy = np.asarray(box)
        items.append(
            {
                "text": text,
                "bbox": [*xy.min(axis=0).tolist(), *xy.max(axis=0).tolist()],
                "confidence": float(score),
            }
        )
print(json.dumps(items, ensure_ascii=False))
