"""CI check inside a real Linux Docker host, not a substitute for public ingress."""
import http.cookiejar
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

base = 'http://127.0.0.1:7860'
report = {'network': 'GitHub-hosted Linux runner -> loopback published Docker port',
          'public_ingress_proven': False, 'answer_mode': 'durable background job',
          'checks': [], 'passed': False}


def request(path, body=None, cookie=None):
    headers = {'Content-Type': 'application/json'}
    if cookie:
        headers['Cookie'] = cookie
    req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None, headers=headers)
    return urllib.request.urlopen(req, timeout=240)


try:
    for attempt in range(180):
        try:
            with request('/api/health') as response:
                if json.load(response)['model_available']:
                    break
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(2)
    else:
        raise RuntimeError('Real model did not become ready')
    report['checks'].append('real_model_ready')
    with request('/') as response:
        assert '<html' in response.read().decode().lower()
    report['checks'].append('frontend_served')
    try:
        request('/api/documents')
        raise AssertionError('Anonymous documents exposed')
    except urllib.error.HTTPError as exc:
        assert exc.code == 401
    report['checks'].append('anonymous_denied')
    with request('/api/account/login', {'name': 'reviewer', 'password': os.environ['MOHENG_REVIEW_PASSWORD']}) as response:
        header = response.headers.get('Set-Cookie', '')
        assert 'secure' in header.lower() and 'httponly' in header.lower()
        cookie = header.split(';')[0]
    # Explicit cookie on loopback is solely a container test; public validation uses HTTPS.
    with request('/api/documents', cookie=cookie) as response:
        docs = json.load(response)
    assert len(docs) >= 2
    paper = next(d for d in docs if d['name'] == '1706.03762v1.pdf')
    with request('/api/documents/' + paper['id'] + '/duplicates', cookie=cookie) as response:
        candidates = json.load(response)
    assert any(d['semantic_status'] == 'ready' and d['recommended_version_id'] for d in candidates)
    report['checks'].append('real_vector_duplicate_detection')
    started = time.monotonic()
    with request('/api/jobs', {'kind': 'ask', 'payload': {'question': 'What GPUs were used to train the Transformer?', 'document_ids': [paper['id']]}}, cookie=cookie) as response:
        job = json.load(response)
    report['job_acceptance_seconds'] = round(time.monotonic() - started, 3)
    assert report['job_acceptance_seconds'] < 15
    assert job.get('id')
    while time.monotonic() - started < 900:
        with request('/api/jobs/' + job['id'], cookie=cookie) as response:
            state = json.load(response)
        if state['state'] == 'completed':
            break
        if state['state'] in {'failed', 'cancelled', 'interrupted'}:
            raise AssertionError('Background task did not complete: ' + state['state'])
        time.sleep(5)
    else:
        raise AssertionError('Background answer exceeded 15 minute acceptance budget')
    with request('/api/jobs/' + job['id'] + '/answer-parts', cookie=cookie) as response:
        parts = json.load(response)
    assert len(parts) == 1
    answer = parts[0]
    report['answer_seconds'] = round(time.monotonic() - started, 3)
    assert answer.get('claims')
    assert 'P100' in json.dumps(answer['claims'], ensure_ascii=False), 'GPU answer missed the source hardware'
    assert answer.get('evidence') and all(e['document_id'] == paper['id'] for e in answer['evidence'])
    report['answer'] = answer
    report['checks'].append('real_scoped_model_answer')
    report['checks'].append('background_job_accepted_quickly_and_result_persisted')
    report['checks'].append('source_gpu_answer_contains_P100')
    report['passed'] = True
finally:
    Path('docker-check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
