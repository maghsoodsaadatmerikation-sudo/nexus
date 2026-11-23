#!/usr/bin/env python3
"""Optional LIVE Europe PMC CORS / JATS smoke probe using the actual Studio reader.

Never part of deterministic CI. Requires a human to pass --live explicitly.
Uses a disposable file:// Chromium origin, not the production web origin.
Only a public PMCID is sent, and no article body is printed or saved.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true',
                        help='Confirm network access to the external Europe PMC service')
    parser.add_argument('--pmcid',default='PMC7029759')
    args=parser.parse_args()
    if not args.live:
        parser.error('Live network probe is disabled unless --live is explicitly passed')
    if not re.fullmatch(r'PMC[1-9][0-9]{0,9}',args.pmcid):
        parser.error('PMCID must match PMC followed by 1-10 decimal digits')
    if not shutil.which('chromium') and not shutil.which('google-chrome'):
        parser.error('Chromium or google-chrome is required')
    module=(ROOT/'web/studio-claim-review.js').read_text(encoding='utf-8')
    pmcid=json.dumps(args.pmcid)
    witness="""window.addEventListener('load',async()=>{
      const destination=document.getElementById('nexus-browser-result');
      try{
       const answer='The year 2025 had a documented article record.';
       // A deliberately synthetic phrase is tested for literal absence, not claim truth.
       const quote='This is a deliberately synthetic NEXUS full text test quotation.';
       const result=await NexusClaimReview.lookupEuropePmcFullText(
        answer,'c1',PMCID,quote,{consent:true}
       );
       if(result.pmcid!==PMCID||!result.source_retrieved||
          result.claim_verified!==false||result.authority!=='none')
        throw Error('unexpected-scope');
       destination.textContent=JSON.stringify({
        status:'PASS',protocol:'real-third-party-CORS',provider:'Europe PMC',
        pmcid:result.pmcid,response_bytes:result.response_bytes,
        sha256:result.response_sha256,doctype_handling:result.doctype_handling,
        article_type:result.article_type_as_deposited,
        claim_verified:false,origin_scope:'disposable-file-origin-not-production'
       });
      }catch(error){
       destination.textContent=JSON.stringify({
        status:'FAIL',reason:String(error?.message||'unknown'),
        protocol:'real-third-party-CORS',pmcid:PMCID,
        claim_verified:false,origin_scope:'disposable-file-origin-not-production'
       });
      }
    });""".replace('PMCID',pmcid)
    html=('<!doctype html><html><head><meta charset="utf-8">'
          '<meta http-equiv="Content-Security-Policy" '
          'content="default-src \'none\'; script-src \'unsafe-inline\'; '
          'connect-src https://www.ebi.ac.uk"></head>'
          '<body><pre id="nexus-browser-result">pending</pre>'
          '<script>'+module+'</script><script>'+witness+'</script></body></html>')
    with tempfile.TemporaryDirectory(prefix='nexus-epmc-live-') as td:
        location=Path(td)/'probe.html'
        location.write_text(html,encoding='utf-8')
        command=['node',str(ROOT/'scripts/workspace-browser-runner.mjs'),
                 'chromium',location.as_uri(),str(Path(td)/'report'),
                 '1280,900','45000','16000']
        proc=subprocess.run(command,capture_output=True,text=True,timeout=80)
        if proc.returncode:
            raise RuntimeError('Live Chromium probe runner failed: '+proc.stderr[-700:])
        result=json.loads(proc.stdout)
        print(json.dumps(result,ensure_ascii=False,sort_keys=True))
        if result.get('status')!='PASS':
            raise SystemExit(1)
if __name__=='__main__':
    main()
