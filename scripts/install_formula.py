"""Install optional CPU formula OCR without changing the main NumPy environment."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
env = ROOT / "tools/formula-env"
python = env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
if not python.exists():
    subprocess.run([sys.executable, "-m", "venv", str(env)], check=True)
subprocess.run(
    [
        str(python),
        "-m",
        "pip",
        "install",
        "-r",
        str(ROOT / "requirements-formula-lock.txt"),
    ],
    check=True,
)
folder = ROOT / "models/formula"
folder.mkdir(parents=True, exist_ok=True)
expected = {
    "image_resizer.onnx": "e0b075c39700f64d50400f39c8fc186bbb3b5d84d31864008313f376603aca9d",
    "encoder.onnx": "01bf5dc25539ca0cd5b1bd29296ea495977a6ba5f629dc4178277809d26e5e7d",
    "decoder.onnx": "bd695497bf1b22279b7626f5916c79226e1e244c84355f8da7edfd2d921d0072",
    "tokenizer.json": "1dc27b18d6a518d0d5ff3f4bb7bd98521fe80ad39e5b2a246d4109f1bb9d5019",
}
base = "https://github.com/RapidAI/RapidLaTeXOCR/releases/download/v0.0.0/"
manifest = []
for name, digest in expected.items():
    path = folder / name
    if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        temporary = path.with_suffix(path.suffix + ".partial")
        with (
            urllib.request.urlopen(base + name, timeout=120) as response,
            temporary.open("wb") as output,
        ):
            while chunk := response.read(1048576):
                output.write(chunk)
        if hashlib.sha256(temporary.read_bytes()).hexdigest() != digest:
            raise ValueError("Formula model checksum mismatch: " + name)
        temporary.replace(path)
    manifest.append(
        {
            "name": name,
            "source": base + name,
            "sha256": digest,
            "size": path.stat().st_size,
        }
    )
    print("Verified", name, flush=True)
(folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
