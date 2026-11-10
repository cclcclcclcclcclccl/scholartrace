"""Download only pinned public assets with hashes; no credentials or private data."""
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest = json.loads((ROOT / 'deploy/assets.json').read_text(encoding='utf-8'))
    for record in manifest:
        target = (ROOT / record['target']).resolve()
        if not target.is_relative_to(ROOT):
            raise ValueError('Invalid asset target')
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            with target.open('rb') as f:
                if hashlib.file_digest(f, 'sha256').hexdigest() == record['sha256']:
                    continue
        partial = target.with_suffix(target.suffix + '.partial')
        error = None
        for url in record['urls']:
            try:
                if not url.startswith('https://'):
                    raise ValueError('HTTPS required')
                with urllib.request.urlopen(url, timeout=120) as source, partial.open('wb') as dest:
                    while chunk := source.read(1024 * 1024):
                        dest.write(chunk)
                with partial.open('rb') as f:
                    if hashlib.file_digest(f, 'sha256').hexdigest() != record['sha256']:
                        raise ValueError('Asset checksum mismatch: ' + record['target'])
                partial.replace(target)
                error = None
                break
            except Exception as exc:
                error = exc
                partial.unlink(missing_ok=True)
        if error:
            raise error
        print('Verified', record['target'], flush=True)


if __name__ == '__main__':
    main()
