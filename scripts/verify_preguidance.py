"""Run the official three PDF classes in an isolated database; retain measurements."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import database, parsing, store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='artifacts/preguidance-20261110/official')
    args = parser.parse_args()
    dest = Path(args.output).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    store.DB_PATH = dest / 'official.sqlite3'
    database.initialize()
    corpus = ROOT / 'data/competition/pdf'
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'cases': [],
              'limits': 'Developer acceptance on supplied official PDFs, not a blind benchmark. OCR text/geometry and extraction coverage do not certify every formula, table or translation.'}

    def document(name):
        source = corpus / name
        with source.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        doc = store.import_pdf(source)
        return doc, {'file': name, 'sha256': digest, 'pages': doc['pages']}

    def run(name, action):
        start = time.monotonic()
        try:
            item = action()
            item.update(case=name, passed=all(item['checks'].values()))
        except Exception as exc:
            item = {'case': name, 'passed': False, 'error': str(exc)}
        item['seconds'] = round(time.monotonic() - start, 3)
        report['cases'].append(item)
        (dest / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(name, item['passed'], item['seconds'], flush=True)

    def versions():
        newer, n = document('1706.03762v7.pdf')
        older, o = document('1706.03762v1.pdf')
        match = store.content_similarity(older['id'], newer['id'])
        unrelated, u = document('N19-1423.pdf')
        control = store.content_similarity(older['id'], unrelated['id'])
        return {'sources': [n, o, u], 'comparison': match, 'negative_control': control,
                'checks': {'real_onnx_body_vectors': match['semantic_status'] == 'ready',
                           'newer_recommended': match['recommended_version_id'] == newer['id'],
                           'unrelated_not_same': not control['likely_same_paper'],
                           'positive_ranks_above_negative': match['semantic_content_cosine'] > control['semantic_content_cosine'],
                           'native_geometry': all(b['bbox'][2] > b['bbox'][0] for b in store.get_blocks(older['id']))}}

    def scan():
        doc, source = document('1706.03762v1_img.pdf')
        pages = []
        for page in range(1, doc['pages'] + 1):
            parsing.ocr_page(doc, page)
            blocks = store.get_blocks(doc['id'], page)
            pages.append({'page': page, 'blocks': len(blocks), 'chars': sum(len(b['text']) for b in blocks)})
            (dest / 'scan-progress.json').write_text(json.dumps(pages), encoding='utf-8')
            print('OCR', page, '/', doc['pages'], flush=True)
        text = ' '.join(b['text'] for b in store.get_blocks(doc['id'])).lower()
        return {'sources': [source], 'pages': pages,
                'checks': {'all_pages_have_text': all(p['chars'] > 20 for p in pages),
                           'title_recovered': 'attention' in text and 'all you need' in text,
                           'training_hardware_recovered': 'p100' in text}}

    def book():
        doc, source = document('UnderstandingDeepLearning_02_09_26_C.pdf')
        blocks = store.get_blocks(doc['id'])
        represented = {b['page'] for b in blocks}
        blank = [i for i in range(1, doc['pages'] + 1) if i not in represented]
        samples = []
        for page in [1, 100, 270, doc['pages']]:
            structure = parsing.page_structure(doc, page)
            samples.append({'page': page, 'structure_keys': sorted(structure), 'block_count': sum(b['page'] == page for b in blocks)})
        return {'sources': [source], 'total_blocks': len(blocks), 'pages_with_native_text': len(represented),
                'pages_without_native_text': blank, 'structure_spotchecks': samples,
                'checks': {'expected_541_pages': doc['pages'] == 541,
                           'last_page_reachable': doc['pages'] in represented,
                           'no_page_number_truncation': all(1 <= b['page'] <= doc['pages'] for b in blocks),
                           'majority_native_text': len(represented) >= .95 * doc['pages']}}

    run('native_versions_and_negative_control', versions)
    run('official_scan_all_pages_ocr', scan)
    run('official_541_page_book', book)
    report['passed'] = all(c['passed'] for c in report['cases'])
    (dest / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
