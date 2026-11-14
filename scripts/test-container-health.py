#!/usr/bin/env python3
"""Docker's actual health engine on isolated default/custom/quarantined gateways."""
import json
import os
import subprocess
import sys
import time

def docker(*args,check=True,timeout=30):
 return subprocess.run(['docker',*args],capture_output=True,text=True,timeout=timeout,check=check)

def main():
 assert os.environ.get('GITHUB_ACTIONS')=='true','ci-only'
 assert not any(os.environ.get(k) for k in ['RAILWAY_TOKEN','RAILWAY_API_TOKEN','RENDER_API_KEY','NEXUS_API_TOKEN']),'external-credentials-present'
 image=sys.argv[1];run=os.environ['GITHUB_RUN_ID'];assert run.isdigit()
 checks=[]
 for label,port,quarantined in [('default',3000,False),('custom',3417,False),('quarantined',3418,True)]:
  name=f'nexus-health-{run}-{label}'
  args=['run','-d','--name',name,'--network','none','--tmpfs','/data:rw,size=8m,mode=0777','--health-interval','1s','--health-start-period','0s','-e','NEXUS_API_TOKEN=synthetic-health-only','-e',f'NEXUS_BIND_ADDR=0.0.0.0:{port}']
  if quarantined:args+=['--entrypoint','/bin/bash']
  args+=[image]
  if quarantined:args+=['-ec','touch /data/.nexus-recovery-required; exec /usr/local/bin/nexus-entrypoint']
  try:
   docker(*args)
   deadline=time.monotonic()+20
   while True:
    state=json.loads(docker('inspect',name).stdout)[0]['State']
    assert state['Running'],label+'-gateway-exited'
    if state.get('Health',{}).get('Status')=='healthy':break
    assert time.monotonic()<deadline,label+'-health-never-became-healthy'
    time.sleep(.2)
   docker('exec',name,'/usr/local/bin/nexus','--health-check')
   checks.append(label+'-actual-docker-health-engine-passes')
   wrong=docker('exec','-e','NEXUS_BIND_ADDR=127.0.0.1:1',name,'/usr/local/bin/nexus','--health-check',check=False)
   assert wrong.returncode!=0;checks.append(label+'-unreachable-port-is-not-healthy')
   if quarantined:
    command=f'exec 3<>/dev/tcp/127.0.0.1/{port}; printf "GET /readyz HTTP/1.1\\r\\nHost: localhost\\r\\nConnection: close\\r\\n\\r\\n" >&3; cat <&3'
    raw=docker('exec',name,'bash','-ec',command).stdout
    assert raw.startswith('HTTP/1.1 503 ') and 'quarantined' in raw
    checks.append('quarantine-remains-not-ready-without-liveness-restart-loop')
  finally:docker('rm','-f',name,check=False)
 print(json.dumps({'status':'PASS','checks':checks,'scope':'disposable-docker-health-engine-only','production_mutation':False,'authority':'none'}))
if __name__=='__main__':main()
