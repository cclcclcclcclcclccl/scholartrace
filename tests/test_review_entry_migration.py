"""A local recovery must not overwrite a verified cloud reviewer entrance."""
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('entry', Path(__file__).resolve().parents[1] / 'scripts/refresh_review_entry.py')
entry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entry)

def test_cloud_entry_survives_local_recovery(tmp_path):
    (tmp_path / 'submission-site').mkdir()
    runtime = tmp_path / 'submission-site/runtime.json'
    original = json.dumps({'hosting': 'modelscope', 'url': 'https://modelscope.cn/studios/cclcclccl/moheng-review'})
    runtime.write_text(original, encoding='utf-8')
    with patch.object(entry, 'ROOT', tmp_path), patch.object(entry.subprocess, 'check_output') as command, patch.object(entry.urllib.request, 'urlopen') as network:
        entry.main()
    command.assert_not_called()
    network.assert_not_called()
    assert runtime.read_text(encoding='utf-8') == original
