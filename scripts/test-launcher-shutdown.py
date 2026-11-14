#!/usr/bin/env python3
"""Real signals and child processes; readiness adapters isolate supervisor shutdown."""
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
WRAPPER=r'''
import json,os,runpy,signal,subprocess,sys,time,types,urllib.request
from pathlib import Path
script,state,marker,mode=sys.argv[1:]
real_popen=subprocess.Popen
child_code="import signal,time; from pathlib import Path; "+("signal.signal(signal.SIGTERM,signal.SIG_IGN); " if mode=='resistant' else '')+"Path("+repr(marker)+").touch(); "+("time.sleep(.3); raise SystemExit("+("0" if mode=='exit-zero' else "7")+")" if mode.startswith('exit-') else "time.sleep(60)")
def spawn(args,**kwargs):return real_popen([sys.executable,'-c',child_code],**kwargs)
subprocess.Popen=spawn
class Response:
 status=200
 def __init__(self,data):self.data=data
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def read(self,n=-1):return json.dumps(self.data).encode()
class Opener:
 def open(self,request,**kwargs):
  stop=time.monotonic()+3
  while not Path(marker).exists():
   if time.monotonic()>stop:raise OSError('child-not-armed')
   time.sleep(.01)
  url=request if isinstance(request,str) else request.full_url
  data=({'status':'ok','scope':'transport-liveness-only'} if url.endswith('/healthz') else {'status':'ready'} if url.endswith('/readyz') else {'configured':False,'authority':'none'})
  return Response(data)
urllib.request.build_opener=lambda *args:Opener()
sys.modules['uvicorn']=types.ModuleType('uvicorn')
model=types.ModuleType('studio_model');model.config=lambda:None;sys.modules['studio_model']=model
sys.argv=[script,'--state-dir',state]+(['--binary',sys.executable,'--port','0'] if script.endswith('run-local-pilot.py') else ['--port','0'])
runpy.run_path(script,run_name='__main__')
'''

def main():
 checks=[]
 with tempfile.TemporaryDirectory(prefix='nexus-shutdown-') as temp:
  root=Path(temp);wrapper=root/'wrapper.py';wrapper.write_text(WRAPPER)
  for launcher in ['pilot','studio']:
   for mode in ['cooperative','resistant','exit-zero','exit-error']:
    for stop_signal in ([None] if mode.startswith('exit-') else [signal.SIGTERM,signal.SIGINT]):
     suffix=stop_signal.name if stop_signal else 'EXIT'
     label=f'{launcher}-{mode}-{suffix}';state=root/label;marker=root/(label+'.armed')
     env={k:v for k,v in os.environ.items() if not k.startswith('NEXUS_')}
     process=subprocess.Popen([sys.executable,str(wrapper),str(ROOT/f'scripts/run-local-{launcher}.py'),str(state),str(marker),mode],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
     child_handle=None
     try:
      assert select.select([process.stdout],[],[],10)[0],label+'-startup-timeout'
      line=process.stdout.readline();assert line,label+'-startup-failed'
      info=json.loads(line);child_handle=os.pidfd_open(info['gateway_pid'])
      started=time.monotonic()
      if stop_signal is not None:process.send_signal(stop_signal)
      out,err=process.communicate(timeout=9)
      expected=1 if mode=='exit-zero' else 7 if mode=='exit-error' else 0
      assert process.returncode==expected,label+'-exit-status'
      assert time.monotonic()-started<8,label+'-unbounded-stop'
      assert select.select([child_handle],[],[],1)[0],label+'-child-survived'
      token=(state/'api-token').read_text().strip();assert token not in line+out+err,label+'-credential-output'
      import fcntl
      with (state/'operator.lock').open('rb') as handle:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
      checks.append(label)
     finally:
      if child_handle is not None:
       try:signal.pidfd_send_signal(child_handle,signal.SIGKILL)
       except ProcessLookupError:pass
       os.close(child_handle)
      if process.poll() is None:process.kill()
      process.communicate(timeout=3)
 print(json.dumps({'status':'PASS','checks':checks,'scope':'real-signal-and-child-lifecycle-with-stubbed-readiness','authority':'none'}))
if __name__=='__main__':main()
