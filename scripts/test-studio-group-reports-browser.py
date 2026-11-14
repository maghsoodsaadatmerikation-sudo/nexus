#!/usr/bin/env python3
"""Full grouped exports, disclosed previews and no work after cancelled file reads."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('studio_browser', ROOT/'scripts/test-studio-browser.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.MIN_CHECKS = 18
module.WITNESS = r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[],assert=(value,label)=>{if(!value)throw Error(label);checks.push(label)};
 const wait=async fn=>{for(let i=0;i<400;i++){if(fn())return;await new Promise(r=>setTimeout(r,15))}throw Error('wait-timeout')};
 const fill=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const select=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('change'))};
 const downloads=[],blobs=new Map(),originalURL=URL.createObjectURL,nativeRead=File.prototype.arrayBuffer,nativeDigest=crypto.subtle.digest;
 URL.createObjectURL=blob=>{const url=originalURL(blob);blobs.set(url,blob);return url};HTMLAnchorElement.prototype.click=function(){downloads.push(blobs.get(this.href))};
 const handle=$('data-run').onclick,tasks=[];$('data-run').onclick=event=>{const result=Promise.resolve(handle(event));tasks.push(result);return result};
 const file=(name,body)=>new File([body],name);
 function choose(f){const dt=new DataTransfer();dt.items.add(f);$('data-file').files=dt.files;$('data-file').dispatchEvent(new Event('change'))}
 function run(){ $('data-run').click();return tasks.at(-1) }
 async function report(){$('data-export').click();return JSON.parse(await downloads.at(-1).text())}
 try{
  window.confirm=()=>true;window.fetch=()=>{throw Error('unexpected-network')};fill('project-title','SYNTHETIC GROUP REPORT');$('new-project').click();
  const csv='Group,Value\n'+Array.from({length:14},(_,i)=>'G'+String(i).padStart(2,'0')+','+i).join('\n');choose(file('fourteen.csv',csv));await run();select('data-group','0');select('data-metric','1');
  const full=await report();assert(full.groups.length===14,'export-retains-every-group-beyond-preview-limit');
  assert(full.groups.reduce((n,g)=>n+g.count,0)===14,'exported-groups-account-for-every-row');assert(full.groups.some(g=>g.label==='G13'&&g.metric_mean===13),'tail-group-retains-its-numeric-result');
  assert(full.group_by==='Group'&&full.metric==='Value','export-identifies-both-selected-columns');assert(full.groups_complete===true&&full.group_count===14,'export-discloses-group-completeness');
  assert($('data-summary').textContent.includes('12/14')&&!$('data-summary').textContent.includes('G13: n='),'summary-discloses-bounded-preview');
  $('data-chart').click();const chart=JSON.parse($('chart-json').value);assert(chart.labels.length===12&&chart.title.includes('12/14'),'chart-identifies-its-preview-coverage');
  select('data-metric','-1');const counted=await report();assert(counted.metric===null&&counted.groups.length===14&&counted.groups.every(g=>g.metric_mean===null),'count-only-export-remains-complete');
  select('data-group','-1');const ungrouped=await report();assert(ungrouped.group_by===null&&ungrouped.group_count===0&&ungrouped.groups.length===0,'no-group-selection-is-explicit');
  choose(file('replacement.csv','Category,Amount\nA,100\nB,200\n'));const count=downloads.length;
  assert(!$('data-summary').textContent&&$('data-export').disabled,'new-file-invalidates-old-report');$('data-export').click();assert(downloads.length===count,'old-report-cannot-be-exported-after-selection-change');
  await run();select('data-group','0');select('data-metric','1');const replacement=await report();assert(replacement.source.sha256!==full.source.sha256&&replacement.group_by==='Category'&&replacement.metric==='Amount','replacement-report-has-current-provenance');

  let release,entered=false;const gate=new Promise(r=>release=r);let digests=0;
  File.prototype.arrayBuffer=async function(){if(this.name==='cancelled.csv'){entered=true;await gate}return nativeRead.call(this)};
  crypto.subtle.digest=function(...args){digests++;return nativeDigest.apply(this,args)};
  choose(file('cancelled.csv','Group,Value\nOLD,999\n'));const cancelled=run();await wait(()=>entered);$('lock').click();const lockedStatus=$('data-status').textContent;release();await cancelled;
  assert(digests===0,'locked-file-read-does-not-start-hashing');assert(!$('data-summary').textContent&&$('data-export').disabled,'locked-read-cannot-restore-an-analysis');assert($('data-status').textContent===lockedStatus,'locked-read-cannot-replace-newer-status');
  File.prototype.arrayBuffer=nativeRead;crypto.subtle.digest=nativeDigest;
  fill('project-title','NEWER ANALYSIS PROJECT');$('new-project').click();let finishOld,oldEntered=false;const oldGate=new Promise(r=>finishOld=r);digests=0;
  File.prototype.arrayBuffer=async function(){if(this.name==='older.csv'){oldEntered=true;await oldGate}return nativeRead.call(this)};
  crypto.subtle.digest=function(...args){digests++;return nativeDigest.apply(this,args)};
  choose(file('older.csv','g,v\nSTALE,999\n'));const old=run();await wait(()=>oldEntered);choose(file('newer.csv','g,v\nCURRENT,7\n'));await run();const current=$('data-summary').textContent;assert(digests===1,'newer-analysis-hashes-its-own-input');finishOld();await old;
  assert(digests===1,'superseded-read-does-not-start-extra-hashing');assert($('data-summary').textContent===current&&current.includes('CURRENT')&&!current.includes('STALE'),'old-result-cannot-replace-newer-analysis');
  select('language','fa');select('data-group','0');assert($('data-summary').textContent.includes('1/1')&&document.documentElement.dir==='rtl','preview-coverage-remains-visible-in-persian');
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,real_files_and_crypto:true,network_requests:0,authority:'none'});
 }catch(error){$('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:error.message,checks})}
 finally{File.prototype.arrayBuffer=nativeRead;crypto.subtle.digest=nativeDigest}
});
"""

if __name__ == '__main__':
    module.main()
