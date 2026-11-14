#!/usr/bin/env python3
"""Compiled Rust health CLI against controlled real HTTP responses; synthetic only."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time

def main():
 binary=Path(sys.argv[1]).resolve(strict=True);checks=[];redirects=[]
 class RedirectTarget(BaseHTTPRequestHandler):
  def do_GET(self):redirects.append(self.path);self.send_response(200);self.end_headers()
  def log_message(self,*args):pass
 target=ThreadingHTTPServer(('127.0.0.1',0),RedirectTarget);target_thread=threading.Thread(target=lambda:target.serve_forever(poll_interval=.05),daemon=True);target_thread.start()
 try:
  with tempfile.TemporaryDirectory(prefix='nexus-health-cli-') as tmp:
   data=Path(tmp)/'must-not-be-created'
   base_env={k:v for k,v in os.environ.items() if not k.startswith('NEXUS_')}
   for mode in ['valid-wildcard','valid-explicit','not-found','wrong-status-body','redirect','wrong-length','duplicate-length','duplicate-status','oversized','slow']:
    requests=[]
    class Handler(BaseHTTPRequestHandler):
     def do_GET(self):
      requests.append((self.path,self.headers.get('authorization')))
      if mode=='slow':time.sleep(2);return
      status=404 if mode=='not-found' else 302 if mode=='redirect' else 200
      body=(b'200 OK' if mode=='not-found' else b'{"status":"ready"}' if mode=='wrong-status-body' else b'{"status":"dead","status":"alive"}' if mode=='duplicate-status' else b'x'*9000 if mode=='oversized' else b'{"status":"alive"}')
      self.send_response(status)
      if mode=='redirect':self.send_header('Location',f'http://127.0.0.1:{target.server_port}/foreign')
      self.send_header('Content-Length',str(0 if mode=='wrong-length' else len(body)))
      if mode=='duplicate-length':self.send_header('Content-Length',str(len(body)))
      self.end_headers()
      try:self.wfile.write(body)
      except (BrokenPipeError,ConnectionResetError):pass
     def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);worker=threading.Thread(target=lambda:server.serve_forever(poll_interval=.05),daemon=True);worker.start()
    try:
     host='127.0.0.1' if mode=='valid-explicit' else '0.0.0.0'
     env=dict(base_env,NEXUS_BIND_ADDR=f'{host}:{server.server_port}',NEXUS_DATA_DIR=str(data))
     if mode!='valid-wildcard':env['NEXUS_API_TOKEN']='synthetic-private-unused'
     started=time.monotonic();result=subprocess.run([str(binary),'--health-check'],env=env,capture_output=True,text=True,timeout=4)
     assert (result.returncode==0)==mode.startswith('valid-'),mode+'-classification'
     assert time.monotonic()-started<3,mode+'-unbounded'
     assert result.stdout==result.stderr=='',mode+'-output'
     assert requests==[('/livez',None)],mode+'-credential-or-route'
     assert not data.exists(),mode+'-created-state'
     checks.append(mode)
    finally:server.shutdown();server.server_close();worker.join(timeout=2)
   for address in ['not-an-address','127.0.0.1:0']:
    result=subprocess.run([str(binary),'--health-check'],env=dict(base_env,NEXUS_BIND_ADDR=address,NEXUS_DATA_DIR=str(data)),capture_output=True,text=True,timeout=3)
    assert result.returncode!=0 and result.stdout==result.stderr=='' and not data.exists()
    checks.append('reject-'+address)
   assert redirects==[],'redirect-contacted-foreign-listener';checks.append('no-redirect-following')
 finally:target.shutdown();target.server_close();target_thread.join(timeout=2)
 print(json.dumps({'status':'PASS','checks':checks,'scope':'real-rust-health-cli-controlled-http','no_credentials_sent':True,'no_data_created':True,'authority':'none'}))
if __name__=='__main__':main()
