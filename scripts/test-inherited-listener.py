#!/usr/bin/env python3
"""Real Rust HTTP acceptance of supervisor-owned listeners; synthetic state only."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

def main():
 binary=Path(sys.argv[1]).resolve(strict=True);checks=[]
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
 with tempfile.TemporaryDirectory(prefix='nexus-inherited-listener-') as temp:
  root=Path(temp);token='synthetic-inherited-listener-only'
  base_env={k:v for k,v in os.environ.items() if not k.startswith('NEXUS_')}
  def environment(label,fd,addr):return dict(base_env,NEXUS_API_TOKEN=token,NEXUS_DATA_DIR=str(root/label),NEXUS_BIND_ADDR=addr,NEXUS_LISTEN_FD=str(fd))
  reserved=socket.socket();reserved.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);reserved.bind(('127.0.0.1',0));reserved.listen(16);fd=reserved.fileno();host,port=reserved.getsockname();addr=f'{host}:{port}'
  process=subprocess.Popen([str(binary)],env=environment('valid',fd,addr),pass_fds=(fd,),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  reserved.close()
  try:
   stop=time.monotonic()+15
   while True:
    assert process.poll() is None,'inherited-gateway-exited'
    try:
     with opener.open(f'http://{addr}/livez',timeout=.3) as response:assert json.load(response)=={'status':'alive'}
     break
    except OSError:
     assert time.monotonic()<stop,'inherited-gateway-startup-timeout';time.sleep(.05)
   checks.append('real-http-listener-uses-exact-reserved-port')
   with opener.open(f'http://{addr}/readyz',timeout=1) as response:assert json.load(response)=={'status':'ready'}
   checks.append('inherited-listener-retains-readiness-contract')
   for bearer,expected in [('wrong',401),(token,404)]:
    request=urllib.request.Request(f'http://{addr}/v1/workspaces/nonexistent',headers={'authorization':'Bearer '+bearer})
    try:opener.open(request,timeout=1);raise AssertionError('unexpected-workspace-response')
    except urllib.error.HTTPError as error:assert error.code==expected
   checks.append('inherited-listener-retains-transport-authentication')
  finally:
   process.terminate()
   try:out,err=process.communicate(timeout=5)
   except subprocess.TimeoutExpired:process.kill();out,err=process.communicate(timeout=3)
   assert token not in out+err,'credential-output'
  def reject(label,fd,addr,pass_fds=()):
   result=subprocess.run([str(binary)],env=environment(label,fd,addr),pass_fds=pass_fds,capture_output=True,text=True,timeout=8)
   assert result.returncode!=0,label+'-accepted';assert token not in result.stdout+result.stderr
   checks.append(label+'-rejected-without-credential-output')
  for fd in [0,1,2,2147483647]:reject('descriptor-'+str(fd),fd,'127.0.0.1:3000')
  with open('/dev/null','rb') as file:reject('regular-file',file.fileno(),'127.0.0.1:3000',(file.fileno(),))
  with socket.socket(type=socket.SOCK_DGRAM) as udp:
   udp.bind(('127.0.0.1',0));reject('datagram',udp.fileno(),f'127.0.0.1:{udp.getsockname()[1]}',(udp.fileno(),))
  with socket.socket() as listener:
   listener.bind(('127.0.0.1',0));listener.listen(2);reject('address-mismatch',listener.fileno(),'127.0.0.1:0',(listener.fileno(),))
 print(json.dumps({'status':'PASS','checks':checks,'scope':'real-rust-inherited-listener-synthetic-only','authority':'none'}))
if __name__=='__main__':main()
