#!/usr/bin/env python3
"""Run actual bundled astronomy with website networking disabled in real Chromium."""
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('studio_browser',ROOT/'scripts/test-studio-browser.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
module.MIN_CHECKS=20
module.WITNESS=r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[];
 const assert=(v,label)=>{if(!v)throw Error(label);checks.push(label)};
 const fill=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const check=(id,value)=>{$(id).checked=value;$(id).dispatchEvent(new Event('input',{bubbles:true}));$(id).dispatchEvent(new Event('change',{bubbles:true}))};
 const wait=async fn=>{for(let i=0;i<400;i++){if(fn())return;await new Promise(r=>setTimeout(r,15))}throw Error('wait-timeout')};
 const project=()=>NexusStudioUI.snapshot().projects.find(p=>p.id===$('projects').value);
 let network=0;window.confirm=()=>true;window.fetch=()=>{network++;throw Error('website-network-disabled')};
 const oldNow=Date.now;Date.now=()=>Date.parse('2026-11-13T12:00:00Z');
 try{
  assert($('sky-tone').checked&&!$('use-astrology').checked&&!$('astro-birth').value,'general-style-default-on-without-personal-profile');
  $('sky-inspect').click();assert($('sky-summary').textContent.includes('astronomy-engine-2.1.19')&&$('sky-summary').textContent.includes('longitude'),'actual-local-ephemeris-inspection-with-network-disabled');assert(network===0,'sky-inspection-makes-no-fetch');
  fill('project-title','OFFLINE SKY PROJECT');$('new-project').click();$('new-thread').click();fill('message','Help me think clearly');$('guide').click();let first=project().threads[0].nodes.at(-1).text;
  assert(first.includes('Local guide')&&!/astrolog|Saturn|Moon|2026-11-13/.test(first),'general-guide-has-no-astrology-announcement');const base=NexusStudio.guide('Help me think clearly',false,{skyTone:false});assert(first.endsWith(base)&&first.length>base.length,'tone-only-prefix-preserves-complete-guide-content');assert(!project().astrology,'general-tone-needs-no-birth-profile');
  check('sky-tone',false);fill('message','Help me think clearly');$('guide').click();assert(project().threads[0].nodes.at(-1).text===base,'disabling-general-tone-restores-ordinary-guide');
  fill('astro-birth','2000-01-01T12:00:00Z');$('astro-local-natal').click();assert(!NexusAstrologyUI.hasDraft(),'unknown-birth-time-not-guessed-offline');check('astro-known',true);$('astro-local-natal').click();assert(NexusAstrologyUI.hasDraft()&&$('astro-summary').textContent.includes('computed'),'offline-natal-computation-is-previewed');$('astro-save').click();assert(project().astrology.natal.provider==='astronomy-engine-2.1.19','local-profile-provenance-kept');
  fill('astro-transit','2026-11-13T12:00:00Z');$('astro-local-transit').click();$('astro-save').click();assert(project().astrology.transit.acquisition==='computed'&&!$('use-astrology').checked,'offline-transit-does-not-enable-natal-personalization');assert(network===0,'entire-local-chart-and-guide-path-has-no-network');
  fill('gateway','https://synthetic.invalid');let posted=null;window.fetch=async(url,options={})=>{if(String(url).endsWith('/status'))return new Response(JSON.stringify({configured:true,configuration_id:'a'.repeat(64),model:'synthetic-model',provider_host:'synthetic.invalid'}));posted=JSON.parse(options.body);return new Response(JSON.stringify({text:'Synthetic response for transport verification.',origin:'model',model:'synthetic-model',authority:'none'}))};
  $('check-model').click();await wait(()=>$('model-status').textContent.includes('synthetic-model'));check('sky-tone',true);fill('message','A new general question');$('prepare').click();
  assert($('request-context').textContent.includes('Presentation preference only')&&$('request-context').textContent.includes('astronomy-engine-2.1.19'),'style-is-inspectable-in-exact-model-review');const request=JSON.parse($('request-context').textContent);assert(!JSON.stringify(request.messages).includes('natal_positions')&&!JSON.stringify(request.messages).includes('longitude'),'general-style-sends-no-planetary-or-personal-data');
  check('consent',true);check('sky-tone',false);assert($('request-review').hidden&&!$('consent').checked,'tone-setting-change-revokes-send-approval');check('sky-tone',true);$('prepare').click();check('consent',true);$('send-model').click();await wait(()=>project().threads[0].nodes.at(-1).origin==='model');assert(JSON.stringify(posted.messages).includes('Presentation preference only')&&!JSON.stringify(posted.messages).includes('2000-01-01T12:00:00Z'),'model-receives-only-selected-style-not-birth-time');assert(!/astrolog|astronomy|آسمان/.test(project().threads[0].nodes.at(-1).text),'reply-does-not-append-tone-provenance');
  $('lock').click();assert(!$('astro-birth').value&&!$('use-astrology').checked,'lock-clears-personal-data-while-general-sky-remains-public');$('language').value='fa';$('language').dispatchEvent(new Event('change'));assert($('sky-card').textContent.includes('لحن عمومی')&&document.documentElement.dir==='rtl','persian-local-sky-settings');
  assert(document.documentElement.scrollWidth<=innerWidth+2,'offline-sky-layout-no-horizontal-overflow');Date.now=oldNow;
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,width:innerWidth,website_requests:network,ephemeris:'actual bundled calculation',model:'synthetic transport only'});
 }catch(e){Date.now=oldNow;$('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:e.message,checks})}
});
"""
if __name__=='__main__':module.main()
