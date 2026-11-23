#!/usr/bin/env python3
"""Integrated NEXUS Studio claim-review action in disposable real Chromium."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
WITNESS=r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[];
 const ok=(yes,label)=>{if(!yes)throw Error(label);checks.push(label)};
 const fill=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const change=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('change',{bubbles:true}))};
 const wait=async fn=>{for(let i=0;i<300;i++){if(fn())return;await new Promise(r=>setTimeout(r,15))}throw Error('wait-timeout')};
 const fingerprint='f'.repeat(64),token='github_pat_'+'A'.repeat(40);
 let discovery=0,sends=0,allRequests=0,crossrefCalls=0,lastCrossrefSignal=null,epmcCalls=0,lastEpmcSignal=null;
 window.confirm=()=>true;
 window.fetch=async(url,opts={})=>{
  allRequests++;
  const target=String(url);
  if(target.startsWith('https://www.ebi.ac.uk/europepmc/webservices/rest/')){
   epmcCalls++;lastEpmcSignal=opts.signal;
   ok(opts.method==='GET'&&opts.credentials==='omit'&&opts.redirect==='error'&&
      opts.mode==='cors'&&opts.referrerPolicy==='no-referrer'&&opts.cache==='no-store',
      'epmc-no-credentials-no-redirect-transport');
   if(target.endsWith('/PMC1234567/fullTextXML')){
    const body='<?xml version="1.0" encoding="utf-8"?>'+
     '<!DOCTYPE article PUBLIC "-//NLM//DTD JATS Journal Publishing DTD 1.2//EN" '+
     '"https://jats.nlm.nih.gov/publishing/1.2/JATS-journalpublishing1.dtd">'+
     '<article article-type="research-article"><front><article-meta><article-id pub-id-type="pmc">1234567</article-id>'+ 
     '<article-id pub-id-type="doi">10.1234/fictional-study.2025</article-id>'+ 
     '<related-article related-article-type="corrected-article" />'+
    '<title-group><article-title>Invented <b>Scientific</b> study</article-title></title-group></article-meta></front>'+
    '<body><sec><title>Study methods</title><p>Introduction: The report counted exactly 200 participants in 2025.'+
    '</p><p>Second paragraph only in the remote XML.</p></sec></body></article>';
    return {ok:true,status:200,url:target,
     headers:new Headers({'content-type':'application/xml'}),body:new Response(body).body};
   }
   if(target.endsWith('/PMC1234568/fullTextXML')){
    return new Promise((resolve,reject)=>opts.signal.addEventListener('abort',
      ()=>reject(Error('epmc-stub-aborted')),{once:true}));
   }
   throw Error('epmc-not-allowlisted');
  }
  if(target.startsWith('https://api.crossref.org/works/')){
   crossrefCalls++;lastCrossrefSignal=opts.signal;
   ok(opts.credentials==='omit'&&opts.redirect==='error'&&opts.mode==='cors'&&
      opts.referrerPolicy==='no-referrer'&&opts.cache==='no-store'&&opts.method==='GET',
      'crossref-privacy-preserving-transport');
   const doi=decodeURIComponent(target.slice('https://api.crossref.org/works/'.length));
   if(doi==='10.5555/slow-request')
    return new Promise((resolve,reject)=>opts.signal.addEventListener('abort',
     ()=>reject(Error('synthetic-aborted')),{once:true}));
   const body=JSON.stringify({message:{DOI:doi,title:['Synthetic <b>citation</b>'],
     publisher:'Synthetic Depositor',published:{'date-parts':[[2025,5,6]]}}});
   return {ok:true,status:200,url:target,
     headers:new Headers({'content-type':'application/vnd.crossref-api-message+json'}),
     body:new Response(body).body};
  }
  if(target.endsWith('/studio-api/status')){discovery++;return Response.json({
    configured:true,model:'synthetic-provider',provider_host:'fixture.invalid',
    configuration_id:fingerprint,reply_receipt_version:1,authority:'none'})}
  if(!target.endsWith('/studio-api/respond')||opts.method!=='POST')throw Error('unreviewed-network');
  sends++;
  return Response.json({origin:'model',authority:'none',
   text:sends===1?'A report in 2025 included 200 patients. Treatment caused improvement.':
     'A result was described in 2026. '+token,
   model:'synthetic-provider',model_slot:'primary',configuration_id:fingerprint});
 };
 try{
  ok(typeof NexusClaimReview==='object','claim-review-module-loaded');
  fill('project-title','Claim Review Synthetic');$('new-project').click();$('new-thread').click();
  fill('gateway','https://fixture.invalid');fill('gateway-token','synthetic-gateway-token');
  change('studio-compose-mode','model');$('studio-compose-model-check').click();
  await wait(()=>NexusStudioUI.modelAvailability().model==='synthetic-provider');
  fill('message','Summarize a synthetic study');$('prepare').click();$('consent').click();$('send-model').click();
  await wait(()=>$('messages').querySelector('[data-chat-review-claims]'));
  const button=$('messages').querySelector('[data-chat-review-claims]');
  ok(button?.textContent==='Review claims','button-under-model-reply');
  ok(!$('messages').querySelector('.claim-review-panel'),'review-opt-in-only');
  let before=allRequests;button.click();
  const panel=$('messages').querySelector('.claim-review-panel');
  ok(!!panel&&panel.querySelectorAll('.claim-review-entry').length===2,'local-per-answer-candidates');
  ok(panel.textContent.includes('not checked or verified')&&panel.textContent.includes('not-checked'),'no-false-fact-check');
  ok(allRequests===before,'review-never-contacts-network');
  ok(!JSON.stringify(NexusStudioUI.snapshot()).includes('claim-review-entry'),'review-not-added-to-archive');
  const source=panel.querySelector('[data-claim-evidence-url]');
  const date=panel.querySelector('[data-claim-evidence-date]');
  const note=panel.querySelector('[data-claim-evidence-note]');
  const assessment=panel.querySelector('[data-claim-evidence-assessment]');
  const save=panel.querySelector('[data-claim-evidence-save]');
  let copied=null,confirmed=0;
  Object.defineProperty(navigator,'clipboard',{configurable:true,value:{
   writeText:async text=>{copied=text}
  }});
  ok(!!source&&!!date&&!!note&&!!assessment&&!!save,'per-claim-manual-evidence-inputs');
  const doiInput=panel.querySelector('[data-claim-crossref-doi]');
  const crossrefButton=panel.querySelector('[data-claim-crossref-fetch]');
  const metadata=panel.querySelector('[data-claim-crossref-result]');
  ok(!!doiInput&&!!crossrefButton&&!!metadata,'crossref-metadata-is-separate-action');
  doiInput.value='10.5555/synthetic-2025';
  let crossrefConsent=0,preCrossref=allRequests;
  window.confirm=()=>{crossrefConsent++;return false};
  crossrefButton.click();
  await new Promise(r=>setTimeout(r,40));
  ok(crossrefConsent===1&&allRequests===preCrossref&&crossrefCalls===0,
    'crossref-requires-explicit-confirmation');
  window.confirm=()=>{crossrefConsent++;return true};
  crossrefButton.click();
  await wait(()=>metadata.textContent.includes('Synthetic <b>citation</b>'));
  ok(crossrefCalls===1&&crossrefConsent===2&&allRequests===preCrossref+1,
    'crossref-only-after-consent');
  ok(metadata.textContent.includes('claim_verified=false')&&
     /^[a-f0-9]{64}$/.test(metadata.textContent.match(/[a-f0-9]{64}/)?.[0]||'')&&
     !JSON.stringify(NexusStudioUI.snapshot()).includes('Synthetic Depositor'),
     'digest-metadata-inert-and-never-saved-to-chat');
  ok(!metadata.querySelector('b'),'crossref-api-title-cannot-render-html');
  const pmcidInput=panel.querySelector('[data-claim-epmc-id]');
  const articleButton=panel.querySelector('[data-claim-epmc-fetch]');
  const articleResult=panel.querySelector('[data-claim-epmc-result]');
  const epmcQuoteInput=panel.querySelector('[data-claim-epmc-quote]');
  ok(!!pmcidInput&&!!articleButton&&!!articleResult&&!!epmcQuoteInput,
    'real-article-quote-review-requires-user-inputs');
  ok(epmcQuoteInput!==panel.querySelector('[data-claim-quote-selection]'),
    'remote-article-quote-is-independent-of-human-paste-quote');
  pmcidInput.value='PMC1234567';
  epmcQuoteInput.value='The report counted exactly 200 participants in 2025.';
  let articleConsent=0;
  let requestsBefore=allRequests;
  window.confirm=()=>{articleConsent++;return false};
  articleButton.click();await new Promise(r=>setTimeout(r,35));
  ok(articleConsent===1&&epmcCalls===0&&allRequests===requestsBefore,
     'no-open-article-lookup-before-consent');
  window.confirm=()=>{articleConsent++;return true};
  articleButton.click();
  await wait(()=>articleResult.textContent.includes('Invented Scientific study'));
  ok(epmcCalls===1&&articleConsent===2&&allRequests===requestsBefore+1,
     'one-approved-fixed-endpoint-article-request');
  ok(articleResult.textContent.includes('claim_verified=false')&&
     articleResult.textContent.includes('present-in-retrieved-body')&&
     /[0-9a-f]{64}/.test(articleResult.textContent),
     'article-presence-is-not-scientific-verification');
  ok(articleResult.textContent.includes('Study methods')&&
     articleResult.textContent.includes('research-article')&&
     articleResult.textContent.includes('10.1234/fictional-study.2025')&&
     articleResult.textContent.includes('corrected-article')&&
     articleResult.textContent.includes('retraction_status_verified=false')&&
     articleResult.textContent.includes('simple-external-declaration-stripped')&&
     !articleResult.textContent.includes('jats.nlm.nih.gov'),
     'safe-external-jats-doctype-stripped-before-xml-parse-and-context-labeled');
  ok(!articleResult.querySelector('b')&&
     !articleResult.textContent.includes('Second paragraph only in the remote XML.'),
     'article-body-and-markup-not-leaked-or-rendered');
  ok(!JSON.stringify(NexusStudioUI.snapshot()).includes('Invented Scientific study'),
     'article-review-not-persisted-in-archive');
  pmcidInput.value='PMC1234567';
  epmcQuoteInput.value='A different sentence that was never inside this open article.';
  articleButton.click();
  await wait(()=>panel.textContent.includes('Exact quotation was not found'));
  ok(epmcCalls===2,'absent-quote-is-not-claim-refutation');
  before=allRequests;

  const opens=[],openButton=panel.querySelector('[data-claim-source-open]');
  const beforeOpen=allRequests;
  let navConfirm=0;
  window.open=(...args)=>{opens.push(args);return null};
  ok(!!openButton,'opt-in-source-navigation-action');
  window.confirm=()=>{navConfirm++;return true};
  source.value='https://127.0.0.1/private';
  openButton.click();
  ok(opens.length===0&&panel.textContent.includes('public-looking domain'),'reject-local-private-target');
  source.value='https://example.org/human-only-source?search=reviewed';
  window.confirm=()=>{navConfirm++;return false};
  openButton.click();
  ok(opens.length===0,'reject-navigation-when-user-declines');
  window.confirm=()=>{navConfirm++;return true};
  openButton.click();
  ok(opens.length===1&&opens[0][0]==='https://example.org/human-only-source?search=reviewed'&&
   opens[0][1]==='_blank'&&opens[0][2]==='noopener,noreferrer',
   'explicit-navigation-after-consent-with-no-referrer');
  ok(allRequests===beforeOpen,'browser-opening-requests-no-background-fetch');
  source.value='https://portal.local/private';
  openButton.click();
  ok(opens.length===1,'local-suffix-not-opened');
  source.value='http://unsafe.example.org';date.value='2025-03-04';assessment.value='supports';
  save.click();
  ok(panel.textContent.includes('Could not add note'),'unsafe-source-refused');
  source.value='https://example.org/human-only-source';
  date.value='2025-03-04';note.value='Human-provided context';
  save.click();
  ok(panel.textContent.includes('Your unverified note is kept'),'valid-user-note-shown-as-unverified');
  ok(!JSON.stringify(NexusStudioUI.snapshot()).includes('human-only-source'),'note-not-stored');
  const pasted=panel.querySelector('[data-claim-quote-source]'),
        quotation=panel.querySelector('[data-claim-quote-selection]');
  ok(!!pasted&&!!quotation,'user-pasted-source-and-exact-quotation-controls');
  pasted.value='Synthetic article states: The report counted exactly 200 participants in 2025. Extra text only in the pasted source.';
  quotation.value='The report counted exactly 200 participants in 2025.';
  save.click();
  ok(panel.textContent.includes('Literal quotation present')&&
    !panel.textContent.includes('Extra text only in the pasted source'),
    'only-verbatim-presence-not-source-content-exposed');
  quotation.value='The article contains a fabricated statement never found here.';
  save.click();
  ok(panel.textContent.includes('Quotation not found'),'quote-mismatch-remains-unverified');
  quotation.value='The report counted exactly 200 participants in 2025.';
  pasted.value+=' github_pat_'+'Z'.repeat(40);
  save.click();
  ok(panel.textContent.includes('Possible credential detected in source text')&&
    !panel.textContent.includes('github_pat_'),'source-secret-block-has-no-value-echo');
  pasted.value=pasted.value.split(' github_pat_')[0];
  save.click();
  ok(panel.textContent.includes('Literal quotation present'),'original-safe-manual-quote-reconfirmed');
  const copy=panel.querySelector('[data-claim-evidence-copy]');
  ok(!!copy&&copied===null,'copy-is-explicit-only');
  window.confirm=()=>{confirmed++;return false};
  copy.click();
  await new Promise(r=>setTimeout(r,20));
  ok(copied===null&&confirmed===1,'cancel-prevents-plaintext-copy');
  window.confirm=()=>{confirmed++;return true};
  copy.click();await wait(()=>copied!==null);
  ok(copied.includes('example.org/human-only-source')&&copied.includes('2025-03-04')&&
     copied.includes('not independently verified'),'source-date-and-limited-authority-in-copy');
  ok(copied.includes('present-in-user-paste')&&
     copied.includes('The report counted exactly 200 participants in 2025')&&
     !copied.includes('Extra text only in the pasted source.'),
     'copied-report-traces-quotation-but-omits-source-document');
  ok(allRequests===before,'manual-annotation-and-copy-never-fetch-external-source');
  // An outstanding DOI request must abort when the reviewer closes the panel.
  doiInput.value='10.5555/slow-request';window.confirm=()=>true;
  crossrefButton.click();await wait(()=>crossrefCalls===2);
  pmcidInput.value='PMC1234568';epmcQuoteInput.value='The report counted exactly 200 participants in 2025.';
  articleButton.click();await wait(()=>epmcCalls===3);
  button.click();ok(!$('messages').querySelector('.claim-review-panel'),'panel-closes-without-mutation');
  ok(lastCrossrefSignal?.aborted,'review-close-aborts-inflight-metadata-fetch');
  ok(lastEpmcSignal?.aborted,'review-close-aborts-inflight-open-article-fetch');
  button.click();
  ok(!$('messages').querySelector('.claim-review-panel').textContent.includes('human-only-source'),
   'closing-panel-discards-manual-notes');
  button.click();
  change('language','fa');
  const fa=$('messages').querySelector('[data-chat-review-claims]');
  ok(fa?.textContent==='بررسی ادعاها','persian-localized-action');
  fa.click();ok($('messages').querySelector('.claim-review-panel').textContent.includes('تأیید نشده'),'persian-unverified-disclosure');
  change('language','en');
  fill('message','A second synthetic question');$('prepare').click();$('consent').click();$('send-model').click();
  await wait(()=>$('messages').querySelectorAll('[data-chat-review-claims]').length===2);
  const sensitive=$('messages').querySelectorAll('[data-chat-review-claims]')[1];
  before=allRequests;sensitive.click();
  const blocked=sensitive.closest('article').querySelector('.claim-review-panel');
  ok(blocked?.textContent.includes('Possible credential detected'),'secrets-block-claim-extraction');
  ok(!blocked.textContent.includes(token)&&!blocked.querySelector('.claim-review-entry'),'no-secret-echo-in-review');
  ok(allRequests===before&&sends===2&&discovery===1,'no-additional-remote-attempt');
  $('lock').click();
  ok(!$('messages').querySelector('.claim-review-panel')&&!JSON.stringify(NexusStudioUI.snapshot()).includes(token),'lock-disposes-transient-review');
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,authority:'none',remote_provider_calls:0});
 }catch(error){
  $('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:String(error.message),checks,authority:'none'});
 }
});
"""

def main():
 browser=next((shutil.which(n) for n in ('chromium','google-chrome') if shutil.which(n)),None)
 if not browser:raise RuntimeError('Chromium is required')
 html=(ROOT/'web/studio.html').read_text().replace(
    '</body>','<pre hidden id="nexus-browser-result"></pre><script>'+WITNESS+'</script></body>')
 with tempfile.TemporaryDirectory(prefix='nexus-chat-claim-review-') as td:
  page=Path(td)/'index.html';page.write_text(html)
  for label,size in [('narrow','420,900'),('wide','1280,900')]:
   cmd=['node',str(ROOT/'scripts/workspace-browser-runner.mjs'),
        browser,page.as_uri(),str(Path(td)/label),size,'60000','18000']
   run=subprocess.run(cmd,capture_output=True,text=True,timeout=130)
   if run.returncode:raise RuntimeError('claim-chat-runner-'+run.stderr[-1200:])
   report=json.loads(run.stdout)
   if report.get('status')!='PASS' or len(report.get('checks',[]))<12:
    raise RuntimeError(json.dumps(report,ensure_ascii=False))
 print('NEXUS integrated chat claim-review: PASS (narrow and wide)')

if __name__=='__main__':main()
