"""Install a pinned Windows runtime without development-cache dependencies."""

import hashlib
import json
import sys
import urllib.request
import zipfile
from pathlib import Path


def main():
    if sys.platform != "win32":
        raise SystemExit("Windows installer; see Dockerfile.model for Linux.")
    release = "b11552"
    asset = f"llama-{release}-bin-win-vulkan-x64.zip"
    expected = "83dc16325b532ba603034719e8377e28ca5093c5d4370141a6522f1a0250386c"
    source = f"https://github.com/ggml-org/llama.cpp/releases/download/{release}/{asset}"
    target = Path("tools/downloads/llama-vulkan.zip")
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest() != expected:
        with urllib.request.urlopen(source, timeout=120) as response:
            content = response.read()
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError("Runtime SHA256 mismatch; nothing extracted")
        target.write_bytes(content)
    dest = Path("tools/llama").resolve()
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target) as archive:
        if any(not (dest / name).resolve().is_relative_to(dest) for name in archive.namelist()):
            raise ValueError("Unsafe archive path")
        if archive.testzip():
            raise ValueError("Invalid runtime archive")
        archive.extractall(dest)
    assert (dest / "llama-server.exe").exists()
    models = Path("models")
    models.mkdir(exist_ok=True)
    for name in ("LICENSE", "README.md"):
        with urllib.request.urlopen(f"https://modelscope.cn/models/Qwen/Qwen3-4B-GGUF/resolve/master/{name}", timeout=30) as response:
            (models / f"Qwen3-4B-{name}").write_bytes(response.read())
    record = Path("artifacts/environment/llama-runtime.json")
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(json.dumps({"release": release, "asset": asset, "source": source, "sha256": expected}, indent=2), encoding="utf-8")
    print("Verified and extracted official runtime", release)


if __name__ == "__main__":
    main()
