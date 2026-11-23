#!/usr/bin/env python3
"""Real Chromium claim-review preview acceptance with the project's existing runner.

Synthetic statements only. No Playwright, provider, secrets or public deployment.
"""
from pathlib import Path
import json
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
WITNESS=r"""
window.addEventListener('load',()=>{
 const $=id=>document.getElementById(id), checks=[];
 const ok=(condition,label)=>{if(!condition)throw Error(label);checks.push(label)};
 let network=0;
 window.fetch=()=>{network++;throw Error('network-forbidden')};
 try{
  ok($('answer')&&$('review')&&$('clear'),'input-and-actions-are-present');
  $('answer').value='A report in 2025 included 200 volunteers. The therapy caused improvement.';
  $('review').click();
  ok(document.querySelectorAll('.claim').length===2,'english-factual-candidates-shown');
  ok($('results').textContent.includes('NOT been verified'),'no-truth-claims');
  $('language').value='fa';
  $('answer').value='آمار این پژوهش شامل ۲۵۰ نفر بوده است.';
  $('review').click();
  ok($('results').textContent.includes('تأیید نشده‌اند'),'persian-language-output');
  ok(document.querySelectorAll('.claim').length===1,'persian-candidate-present');
  const synthetic='github_pat_'+'A'.repeat(40);
  $('answer').value='The result was found in 2025. '+synthetic;
  $('review').click();
  ok(document.querySelectorAll('.claim').length===0,'credential-blocks-output');
  ok(!$('results').textContent.includes(synthetic),'credential-value-not-echoed');
  $('clear').click();
  ok(!$('answer').value&&!$('results').textContent,'clear-is-complete');
  ok(network===0,'local-workflow-makes-no-network-calls');
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,authority:'none'});
 }catch(error){
  $('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:String(error.message),checks});
 }
});
"""

def main():
    browser=next((shutil.which(n) for n in ('chromium','google-chrome') if shutil.which(n)),None)
    if not browser:
        raise RuntimeError('Real Chromium required')
    html=(ROOT/'web/studio-claim-review-demo.html').read_text()
    html=html.replace('<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'self\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'; connect-src \'none\'">','')
    html=html.replace('<script src="studio-claim-review.js"></script>','')
    html=html.replace('<script src="studio-claim-review-demo.js"></script>','')
    assert '<script src=' not in html
    script=''.join('<script>'+ (ROOT/'web'/f).read_text()+'</script>' for f in (
        'studio-claim-review.js','studio-claim-review-demo.js'))
    html=html.replace('</body>',script+'<pre id="nexus-browser-result" hidden></pre><script>'+WITNESS+'</script></body>')
    with tempfile.TemporaryDirectory(prefix='nexus-claim-review-') as td:
        page=Path(td)/'index.html'
        page.write_text(html)
        for label,size in [('narrow','420,900'),('wide','1280,900')]:
            run=subprocess.run([
                'node',str(ROOT/'scripts/workspace-browser-runner.mjs'),
                browser,page.as_uri(),str(Path(td)/label),size,'60000','15000'
            ],capture_output=True,text=True,timeout=100)
            if run.returncode:
                raise RuntimeError('claim-review-browser-'+run.stderr[-1200:])
            report=json.loads(run.stdout)
            if report.get('status')!='PASS' or len(report.get('checks',[]))<9:
                raise RuntimeError(json.dumps(report,ensure_ascii=False))
    print('NEXUS claim review Chromium: PASS (narrow and wide)')

if __name__=='__main__':main()
