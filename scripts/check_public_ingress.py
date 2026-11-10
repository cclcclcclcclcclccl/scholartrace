"""Read-only independent-network check; no reviewer credentials are transferred."""
import json
from pathlib import Path
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone

report = {'checked_at': datetime.now(timezone.utc).isoformat(),
          'probe': 'GitHub-hosted ubuntu runner, independent of author machine network',
          'authenticated_flow_tested': False, 'continuous_uptime_proven': False, 'passed': False}


def fetch(url):
    return urllib.request.urlopen(url, timeout=40)


try:
    fixed = 'https://cclcclcclcclcclccl.github.io/scholartrace/'
    with fetch(fixed + 'workbench.html') as response:
        assert response.status == 200
    with fetch(fixed + 'runtime.json') as response:
        runtime = json.load(response)
    url = runtime['url'].rstrip('/')
    assert re.fullmatch(r'https://[a-z0-9-]+\.trycloudflare\.com', url), 'Unexpected host; update allowlist after approved cloud migration'
    report['target'] = url
    with fetch(url) as response:
        assert '<html' in response.read().decode().lower()
    with fetch(url + '/api/health') as response:
        health = json.load(response)
    report['health'] = health
    assert health.get('service') == 'scholartrace' and health.get('model_available')
    try:
        fetch(url + '/api/documents')
        raise AssertionError('Anonymous library exposed')
    except urllib.error.HTTPError as exc:
        assert exc.code == 401
    report['passed'] = True
finally:
    Path('external-check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
