#!/usr/bin/env python3
"""Real Studio DOM/crypto witness; provider calls are deterministic source fixtures."""
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('studio_browser',ROOT/'scripts/test-studio-browser.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
WITNESS=r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[];
 const assert=(v,label)=>{if(!v)throw Error(label);checks.push(label)};
 const fill=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const check=(id,value)=>{$(id).checked=value;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const wait=async fn=>{for(let i=0;i<400;i++){if(fn())return;await new Promise(r=>setTimeout(r,15))}throw Error('wait-timeout')};
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));
 const snapshot=()=>NexusStudioUI.snapshot(),project=()=>snapshot().projects.find(p=>p.id===$('projects').value);
 const natal=__NATAL__,transit=__TRANSIT__;
 let calls=[],late=false,release,posted;
 window.confirm=()=>true;
 window.fetch=async(url,options={})=>{
  if(String(url).startsWith('https://app.on-lineastrology.com/api/positions.php')){
   const u=new URL(url);calls.push({url:String(url),options});assert(options.credentials==='omit'&&options.redirect==='error'&&options.referrerPolicy==='no-referrer','astro-provider-privacy-options');assert([...u.searchParams.keys()].join(',')==='dt,bodies','only-reviewed-time-and-planets-sent');assert(!String(url).includes('TRANSIENT_SECRET'),'gateway-token-never-shared-with-astro-provider');
   const fixture=u.searchParams.get('dt')===natal.input.datetime_utc?natal:transit;
   const response=()=>new Response(JSON.stringify(fixture));if(late)return new Promise(resolve=>release=()=>resolve(response()));return response();
  }
  if(String(url).endsWith('/studio-api/status'))return new Response(JSON.stringify({configured:true,configuration_id:'a'.repeat(64),model:'synthetic-model',provider_host:'synthetic.invalid'}));
  posted=JSON.parse(options.body);return new Response(JSON.stringify({text:'Synthetic transport fixture',origin:'model',model:'synthetic-model',authority:'none'}));
 };
 try{
  assert(calls.length===0&&!$('use-astrology').checked&&!$('astro-birth').value,'no-background-fetch-or-autofilled-birth-data');
  fill('project-title','ASTRO SYNTHETIC PROJECT');$('new-project').click();$('new-thread').click();fill('gateway-token','TRANSIENT_SECRET');
  fill('astro-birth','2000-01-01T16:30:00+04:30');$('astro-prepare-natal').click();assert($('astro-request').hidden&&calls.length===0,'unknown-birth-time-is-not-guessed');check('astro-known',true);$('astro-prepare-natal').click();assert(!$('astro-request').hidden&&$('astro-request-url').textContent.includes('12%3A00%3A00Z'),'utc-offset-normalized-before-consent');
  $('astro-fetch').click();assert(calls.length===0,'no-astro-request-without-consent');check('astro-network-consent',true);fill('astro-orb','1.5');assert($('astro-request').hidden&&!$('astro-network-consent').checked,'edited-request-revokes-network-consent');
  fill('astro-orb','2');$('astro-prepare-natal').click();check('astro-network-consent',true);$('astro-fetch').click();await wait(()=>$('astro-summary').textContent.includes('280')||$('astro-summary').textContent.includes('Capricorn'));
  assert(!project().astrology,'retrieval-does-not-apply-personalization');$('backup').click();assert($('status').textContent.includes('save document versions'),'unapplied-astrology-draft-cannot-be-silently-excluded-from-backup');$('astro-save').click();assert(project().astrology.natal.at==='2000-01-01T12:00:00Z'&&$('use-astrology').disabled,'natal-profile-applied-explicitly-without-fake-transit');
  fill('astro-transit','2026-11-13T12:00:00Z');$('astro-prepare-transit').click();const request=$('astro-request-url').textContent;assert(!request.includes('2000')&&!request.includes('lat=')&&!request.includes('lon='),'transit-request-omits-birth-and-location');check('astro-network-consent',true);$('astro-fetch').click();await wait(()=>$('astro-summary').textContent.includes('Major contacts'));
  $('astro-save').click();assert(project().astrology.transit.at==='2026-11-13T12:00:00Z'&&!$('use-astrology').checked,'applied-transit-does-not-enable-personalization');
  fill('message','What should I reflect on?');$('guide').click();assert(!project().threads[0].nodes.at(-1).text.includes('Personalized local reflection'),'local-guide-neutral-when-disabled');
  check('use-astrology',true);check('astro-historical',true);fill('message','Help me reflect on my current choices.');$('guide').click();assert(project().threads[0].nodes.at(-1).text.includes('Personalized local reflection')&&project().threads[0].nodes.at(-1).text.includes('2026-11-13T12:00:00Z'),'guide-personalization-uses-actual-applied-contacts');
  fill('gateway','https://synthetic.invalid');$('check-model').click();await wait(()=>$('model-status').textContent.includes('synthetic-model'));fill('message','Another question');$('prepare').click();assert($('request-context').textContent.includes('optional-symbolic-astrology')&&!$('request-context').textContent.includes('2000-01-01T12:00:00Z'),'model-review-shows-personalization-without-birth-instant');
  check('consent',true);$('send-model').click();await wait(()=>project().threads[0].nodes.at(-1).origin==='model');assert(JSON.stringify(posted.messages).includes('optional-symbolic-astrology')&&!JSON.stringify(posted).includes('TRANSIENT_SECRET'),'approved-model-context-has-exact-selected-astrology');
  fill('message','No astrology for this answer');$('prepare').click();check('consent',true);check('use-astrology',false);assert($('request-review').hidden&&!$('consent').checked,'opting-out-invalidates-model-approval');$('prepare').click();assert(!$('request-context').textContent.includes('optional-symbolic-astrology')&&$('request-context').textContent.includes('personalization is off'),'disabled-context-does-not-reinsert-chart');fill('message','');
  fill('passphrase','synthetic private password 123');fill('repeat-passphrase','synthetic private password 123');$('create-vault').click();await wait(()=>!$('save').disabled);$('save').click();await wait(()=>$('status').textContent.includes('session saved'));const cipher=await new NexusStudio.IndexedStore().read();assert(!cipher.includes('2000-01-01')&&!cipher.includes('\"astrology\"'),'astro-profile-is-encrypted-at-rest');
  $('lock').click();assert(!$('astro-birth').value&&!$('astro-transit').value&&!$('astro-summary').textContent.includes('2000')&&!$('use-astrology').checked,'lock-clears-astrology-inputs-and-output');fill('passphrase','synthetic private password 123');$('unlock').click();await wait(()=>project()?.astrology?.transit);assert(!$('use-astrology').checked,'encrypted-reopen-does-not-enable-personalization');
  late=true;$('astro-prepare-transit').click();check('astro-network-consent',true);$('astro-fetch').click();await wait(()=>release);$('astro-delete').click();release();await sleep(40);assert(!project().astrology&&!$('use-astrology').checked&&!$('astro-birth').value,'delete-revokes-profile-and-discards-late-source-result');
  fill('project-title','SECOND SYNTHETIC PROJECT');$('new-project').click();assert(!project().astrology&&!$('astro-birth').value,'profiles-isolated-between-projects');
  $('language').value='fa';$('language').dispatchEvent(new Event('change'));assert($('astrology-card').textContent.includes('ترنزیت شخصی')&&document.documentElement.dir==='rtl','persian-astrology-interface');
  assert(document.documentElement.scrollWidth<=innerWidth+2,'astrology-layout-has-no-horizontal-overflow');
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,width:innerWidth,real_model_tested:false,provider_network:'synthetic-fixtures-only',authority:'none'});
 }catch(e){$('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:e.message,checks})}
});
"""
module.WITNESS=WITNESS.replace('__NATAL__',json.dumps(json.loads((ROOT/'tests/fixtures/astrology/on-line-astrology-j2000.json').read_text()))).replace('__TRANSIT__',json.dumps(json.loads((ROOT/'tests/fixtures/astrology/on-line-astrology-transit.json').read_text())))
if __name__=='__main__':module.main()
