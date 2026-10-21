"""Download a pinned public model candidate; verify published SHA256 before use."""

import hashlib
import json
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
NAME = "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
EXPECTED = "3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597"
URL = (
    "https://modelscope.cn/models/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/0b0406b39725d752255ffeb48f102c66f98e14aa/"
    + NAME
)


def main():
    (ROOT / "models").mkdir(exist_ok=True)
    (ROOT / "artifacts/attack-v10").mkdir(parents=True, exist_ok=True)
    path = ROOT / "models" / NAME
    part = path.with_suffix(".gguf.part")
    report = {
        "source": URL,
        "expected_sha256": EXPECTED,
        "status": "starting",
        "weights_trained": False,
    }
    try:
        with httpx.Client(
            timeout=httpx.Timeout(60, connect=20), follow_redirects=True
        ) as client:
            for filename, revision, expected in [
                (
                    "LICENSE",
                    "2bf98c551bf16e880d12db61cece039fb7f74aea",
                    "832dd9e00a68dd83b3c3fb9f5588dad7dcf337a0db50f7d9483f310cd292e92e",
                ),
                (
                    "README.md",
                    "1c6db7f618589b3a51ec5981f75da13fbff11bb0",
                    "8e3dd0c3b5b11897cc71092ccfe517bb7a9783479baa3665aad73c8d1a2041cd",
                ),
            ]:
                r = client.get(
                    "https://modelscope.cn/models/Qwen/Qwen3-4B-Instruct-2507/resolve/"
                    + revision
                    + "/"
                    + filename
                )
                r.raise_for_status()
                assert hashlib.sha256(r.content).hexdigest() == expected
                (ROOT / "models" / ("Qwen3-4B-Instruct-2507-" + filename)).write_bytes(
                    r.content
                )
            if not path.exists():
                start = part.stat().st_size if part.exists() else 0
                with client.stream(
                    "GET", URL, headers={"Range": f"bytes={start}-"} if start else {}
                ) as r:
                    r.raise_for_status()
                    if start and (
                        r.status_code != 206
                        or not r.headers.get("content-range", "").startswith(
                            f"bytes {start}-"
                        )
                    ):
                        raise ValueError("Resume unsupported; partial file preserved")
                    written, last = start, time.monotonic()
                    with part.open("ab" if start else "wb") as f:
                        for chunk in r.iter_bytes(1024 * 1024):
                            f.write(chunk)
                            written += len(chunk)
                            if time.monotonic() - last > 20:
                                print(f"Downloaded {written} / 2497281120", flush=True)
                                last = time.monotonic()
                assert part.stat().st_size == 2497281120
                with part.open("rb") as f:
                    assert hashlib.file_digest(f, "sha256").hexdigest() == EXPECTED
                part.rename(path)
            with path.open("rb") as f:
                digest = hashlib.file_digest(f, "sha256").hexdigest()
            assert digest == EXPECTED
            report.update(status="verified", sha256=digest, bytes=path.stat().st_size)
    except (httpx.HTTPError, OSError, ValueError, AssertionError) as e:
        report.update(status="failed", error=type(e).__name__ + ": " + str(e)[:400])
    (ROOT / "artifacts/attack-v10/model-download-modelscope.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report), flush=True)
    if report["status"] != "verified":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
