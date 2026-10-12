"""Download a pinned public multilingual ONNX model; verify upstream SHA-256."""

import hashlib
import json
from pathlib import Path
import urllib.request

root = Path(__file__).resolve().parents[1]
folder = root / "models/multilingual-minilm"
folder.mkdir(parents=True, exist_ok=True)
repo = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
base = "https://modelscope.cn"
with urllib.request.urlopen(
    f"{base}/api/v1/models/{repo}/repo/files?Revision=master&Recursive=true", timeout=30
) as response:
    files = {f["Path"]: f for f in json.load(response)["Data"]["Files"]}
names = [
    "onnx/model_quint8_avx2.onnx",
    "tokenizer.json",
    "tokenizer_config.json",
    "config.json",
    "README.md",
]
if "LICENSE" in files:
    names.append("LICENSE")
manifest = []
for name in names:
    record = files[name]
    path = folder / Path(name).name
    url = f"{base}/models/{repo}/resolve/{record['Revision']}/{name}"
    if (
        not path.exists()
        or hashlib.sha256(path.read_bytes()).hexdigest() != record["Sha256"]
    ):
        print("Downloading", name, record["Size"], flush=True)
        temporary = path.with_suffix(path.suffix + ".partial")
        with (
            urllib.request.urlopen(url, timeout=120) as source,
            temporary.open("wb") as output,
        ):
            while chunk := source.read(1024 * 1024):
                output.write(chunk)
        digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
        if digest != record["Sha256"]:
            raise ValueError("Model checksum mismatch")
        temporary.replace(path)
    manifest.append(
        {"path": name, "sha256": record["Sha256"], "size": record["Size"], "url": url}
    )
    print("Verified", name, flush=True)
(folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
