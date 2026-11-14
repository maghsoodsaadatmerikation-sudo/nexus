#!/usr/bin/env python3
"""An unrelated loopback listener must never receive the saved gateway token."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import importlib.util
import urllib.request
import urllib.error
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
ROOT=Path(__file__).resolve().parents[1]

def protocol_checks():
 spec=importlib.util.spec_from_file_location('pilot',ROOT/'scripts/run-local-pilot.py');pilot=importlib.util.module_from_spec(spec);spec.loader.exec_module(pilot)
 class Response:
  def __init__(self,status,body):self.status=status;self.body=body
  def read(self,n):assert n==4097;return self.body[:n]
 for status,body in [(200,b'{"status":"ready"}'),(503,b'{"status":"quarantined"}')]:assert pilot.readiness_status(Response(status,body))==status
 for status,body in [(200,b''),(200,b'not-json'),(200,b'\xff'),(200,b'{"status":"quarantined"}'),(503,b'{"status":"ready"}'),(404,b'{"status":"ready"}'),(200,b'{"status":"ready","extra":true}'),(200,b' '*4097)]:
  try:pilot.readiness_status(Response(status,body));raise AssertionError('bad-readiness-accepted')
  except OSError:pass
 received=[]
 class Target(BaseHTTPRequestHandler):
  def do_GET(self):received.append(self.headers.get('authorization'));self.send_response(200);self.end_headers()
  def log_message(self,*args):pass
 target=ThreadingHTTPServer(('127.0.0.1',0),Target)
 class Redirect(BaseHTTPRequestHandler):
  def do_GET(self):self.send_response(int(self.path[1:]));self.send_header('Location',f'http://127.0.0.1:{target.server_port}/foreign');self.send_header('Content-Length','0');self.end_headers()
  def log_message(self,*args):pass
 redirect=ThreadingHTTPServer(('127.0.0.1',0),Redirect)
 threads=[threading.Thread(target=server.serve_forever,daemon=True) for server in [target,redirect]]
 for thread in threads:thread.start()
 try:
  for status in [301,302,303,307,308]:
   request=urllib.request.Request(f'http://127.0.0.1:{redirect.server_port}/{status}',headers={'authorization':'Bearer synthetic-only'})
   try:pilot.local_opener().open(request,timeout=1);raise AssertionError('redirect-followed')
   except urllib.error.HTTPError as error:assert error.code==status
  assert received==[],'redirect-target-received-startup-bearer'
 finally:
  for server in [target,redirect]:server.shutdown();server.server_close()
  for thread in threads:thread.join(timeout=2)

def main():
 seen=[]
 class Foreign(BaseHTTPRequestHandler):
  def do_GET(self):
   seen.append(self.headers.get('authorization'))
   body=b'{"status":"ready"}'
   self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
  def log_message(self,*args):pass
 server=ThreadingHTTPServer(('127.0.0.1',0),Foreign);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 try:
  with tempfile.TemporaryDirectory(prefix='nexus-port-owner-') as tmp:
   root=Path(tmp);state=root/'state';state.mkdir(mode=0o700)
   token='a'*64;(state/'api-token').write_text(token+'\n');(state/'api-token').chmod(0o600)
   binary=root/'unrelated.py';binary.write_text('#!'+sys.executable+'\nimport time\ntime.sleep(60)\n');binary.chmod(0o700)
   env={k:v for k,v in os.environ.items() if not k.startswith('NEXUS_')}
   process=subprocess.Popen([sys.executable,str(ROOT/'scripts/run-local-pilot.py'),'--binary',str(binary),'--state-dir',str(state),'--port',str(server.server_port)],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
   try:
    deadline=time.monotonic()+2
    while process.poll() is None and not seen and time.monotonic()<deadline:time.sleep(.01)
    assert not seen,'foreign-listener-received-a-startup-request-or-credential'
    out,err=process.communicate(timeout=2)
    assert process.returncode==1 and not out and 'BLOCKED' in err
    assert token not in out+err and (state/'api-token').read_text()==token+'\n'
   finally:
    try:os.killpg(process.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    process.communicate(timeout=3)
 finally:server.shutdown();server.server_close();thread.join(timeout=2)
 protocol_checks()
 print(json.dumps({'status':'PASS','checks':['occupied-port-blocks-startup','foreign-listener-receives-no-request-or-bearer','saved-token-preserved','no-false-ready-result','readiness-status-and-body-must-agree','malformed-and-oversized-readiness-rejected','redirects-never-forward-startup-bearer'],'authority':'none'}))
if __name__=='__main__':main()
