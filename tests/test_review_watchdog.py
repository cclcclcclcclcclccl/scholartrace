"""Exercise watchdog health parsing and recovery with isolated files and HTTP."""
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import patch
import unittest
spec=importlib.util.spec_from_file_location('watchdog',Path(__file__).resolve().parents[1]/'scripts/review_watchdog.py');w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  self.send_response(200);self.end_headers();self.wfile.write(json.dumps({'service':'scholartrace','model_available':False}).encode())
 def log_message(self,*args):pass
class WatchdogTests(unittest.TestCase):
 def test_loading_model_is_not_healthy(self):
  server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  try:
   result=w.health('http://127.0.0.1:'+str(server.server_port),True)
   self.assertTrue(result['reachable']);self.assertFalse(result['model_available']);self.assertFalse(w.healthy({'local':result,'public':result}))
  finally:server.shutdown();server.server_close();thread.join()
 def exercise(self,states):
  with tempfile.TemporaryDirectory() as tmp:
   folder=Path(tmp);counter=0
   def check():
    nonlocal counter
    state=states[min(counter,len(states)-1)];counter+=1
    if counter==len(states): (folder/'stop.request').touch()
    return {'local':{'reachable':state,'model_available':state},'public':{'reachable':state,'model_available':state}}
   with patch.object(w,'STATE',folder),patch.object(w,'STOP',folder/'stop.request'),patch.object(w,'check',check),patch.object(w.time,'sleep'),patch.object(w.subprocess,'run') as run:
    run.return_value.returncode=0;w.serve()
    logs=[json.loads(line) for f in folder.glob('health-*.jsonl') for line in f.read_text(encoding='utf-8').splitlines()]
    return run.call_count,logs,json.loads((folder/'status.json').read_text(encoding='utf-8'))
 def test_transient_failure_does_not_restart(self):
  calls,logs,status=self.exercise([False,True]);self.assertEqual(calls,0);self.assertEqual(status['failed_samples'],1);self.assertTrue(status['stopped'])
 def test_sustained_failure_recovers_once_and_preserves_failed_sample(self):
  calls,logs,status=self.exercise([False,False,False,True]);self.assertEqual(calls,1);self.assertEqual(status['failed_samples'],3);self.assertEqual(logs[1]['recovery_exit_code'],0);self.assertFalse(logs[1]['public']['reachable'])
if __name__=='__main__':unittest.main()
