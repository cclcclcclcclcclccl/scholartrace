"""Isolated CPU formula inference. Called with a trusted project-local crop path."""

import json
from pathlib import Path
import sys
import numpy as np
from rapid_latex_ocr import LaTeXOCR
from rapid_latex_ocr.utils_load import OrtInferSession

ROOT = Path(__file__).resolve().parents[1]
folder = ROOT / "models/formula"
source = Path(sys.argv[1]).resolve()
if not (
    source.is_relative_to(ROOT / "data") or source.is_relative_to(ROOT / "artifacts")
):
    raise ValueError("Formula input must be a project-local source crop")
names = ["image_resizer.onnx", "encoder.onnx", "decoder.onnx", "tokenizer.json"]
if not all((folder / name).is_file() for name in names):
    raise ValueError("Run scripts/install_formula.py before requesting recognition")
original = OrtInferSession.__init__


def limited(self, model_path, num_threads=2):
    original(self, model_path, num_threads=2)


OrtInferSession.__init__ = limited
np.random.seed(0)
engine = LaTeXOCR(
    image_resizer_path=folder / names[0],
    encoder_path=folder / names[1],
    decoder_path=folder / names[2],
    tokenizer_json=folder / names[3],
)
latex, elapsed = engine(source)
print(json.dumps({"latex": latex, "seconds": elapsed}, ensure_ascii=False))
