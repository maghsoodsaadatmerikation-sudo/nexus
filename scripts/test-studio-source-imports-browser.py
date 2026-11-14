#!/usr/bin/env python3
"""Actual source files: complete batches, atomic rejection and cancellation isolation."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('studio_browser', ROOT/'scripts/test-studio-browser.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.MIN_CHECKS = 18
module.WITNESS = r"""
window.addEventListener('load',async()=>{
 const S=NexusStudio,$=id=>document.getElementById(id),checks=[],assert=(v,label)=>{if(!v)throw Error(label);checks.push(label)};
 const fill=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const wait=async fn=>{for(let i=0;i<400;i++){if(fn())return;await new Promise(r=>setTimeout(r,15))}throw Error('wait-timeout')};
 const snapshot=()=>JSON.stringify(NexusStudioUI.snapshot()),project=()=>NexusStudioUI.snapshot().projects.find(p=>p.id===$('projects').value);
 const file=(name,text)=>new File([text],name),handle=$('source-file').onchange,tasks=[],native=File.prototype.arrayBuffer,delays=new Map();let reads=0;
 $('source-file').onchange=event=>{const task=Promise.resolve(handle(event));tasks.push(task);return task};
 File.prototype.arrayBuffer=async function(){reads++;const delay=delays.get(this.name);if(delay){delay.entered=true;await delay.gate}return native.call(this)};
 function upload(files){const dt=new DataTransfer();for(const f of files)dt.items.add(f);$('source-file').files=dt.files;$('source-file').dispatchEvent(new Event('change'));return tasks.at(-1)}
 function pause(name){let resolve,reject;const delay={entered:false,gate:new Promise((a,b)=>{resolve=a;reject=b})};delays.set(name,delay);return {ready:()=>delay.entered,resolve,reject}}
 const create=name=>{fill('project-title',name);$('new-project').click()};
 try{
  window.confirm=()=>true;window.fetch=()=>{throw Error('unexpected-network')};create('SYNTHETIC SOURCE PROJECT');
  await upload([file('first.txt','First orchard source'),file('second.md','Second moon source')]);
  assert(project().sources.length===2,'all-selected-source-files-are-imported');
  assert(project().sources.map(s=>s.name).join('|')==='first.txt|second.md','selected-file-order-is-preserved');
  assert(project().sources[1].text==='Second moon source','source-text-is-decoded-correctly');
  const before=snapshot();await upload([file('valid.txt','Must not be added'),file('invalid.txt',new Uint8Array([255,254]))]);
  assert(snapshot()===before,'invalid-utf8-rejects-the-whole-batch');assert($('status').textContent.includes('Operation failed'),'invalid-batch-reports-failure');
  const noReads=reads;await upload([file('valid.txt','Not read'),file('unsupported.pdf','No binary parser')]);assert(reads===noReads&&snapshot()===before,'invalid-metadata-is-rejected-before-any-file-read');
  await upload([file('empty.txt','   '),file('valid.txt','Not added')]);assert(snapshot()===before,'empty-source-rejects-the-whole-batch');
  const oversized=reads;await upload([file('huge.txt','x'.repeat(262145))]);assert(reads===oversized&&snapshot()===before,'oversized-source-is-rejected-before-reading');
  await upload(Array.from({length:10},(_,i)=>file('source-'+i+'.txt','Source '+i)));assert(project().sources.length===12,'batch-can-fill-twelve-source-capacity');
  const full=snapshot(),atCapacity=reads;await upload([file('extra.txt','Not read')]);assert(snapshot()===full&&reads===atCapacity,'capacity-rejection-keeps-existing-sources-and-skips-reading');

  create('CANCELLATION PROJECT');const slow=pause('stopped.txt'),stopped=upload([file('stopped.txt','Stale first'),file('not-read.txt','Stale second')]);await wait(slow.ready);
  assert($('source-file').disabled&&!$('stop').disabled,'batch-has-one-visible-operation-and-can-be-stopped');
  const busyReads=reads;await upload([file('busy.txt','Ignored')]);assert(reads===busyReads,'programmatic-busy-selection-is-ignored');
  $('stop').click();create('NEWER WORK');const newer=snapshot(),afterStopReads=reads;slow.resolve();await stopped;
  assert(snapshot()===newer,'stopped-batch-cannot-change-newer-project');assert(reads===afterStopReads,'cancelled-batch-does-not-read-the-next-file');

  const locked=pause('locked.txt'),pendingLocked=upload([file('locked.txt','Private stale source')]);await wait(locked.ready);$('lock').click();const lockedStatus=$('status').textContent;locked.resolve();await pendingLocked;
  assert(NexusStudioUI.snapshot().projects.length===0,'late-success-cannot-repopulate-locked-work');assert($('status').textContent===lockedStatus,'late-success-cannot-change-locked-status');
  create('FAILURE PROJECT');const failed=pause('failed.txt'),pendingFailure=upload([file('failed.txt','Stale failure')]);await wait(failed.ready);$('lock').click();const failureStatus=$('status').textContent;failed.reject(Error('PRIVATE_READ_FAILURE'));await pendingFailure;
  assert($('status').textContent===failureStatus&&NexusStudioUI.snapshot().projects.length===0,'late-file-failure-does-not-change-locked-work');

  create('LATEST BATCH PROJECT');const older=pause('older.txt'),old=upload([file('older.txt','Discarded source')]);await wait(older.ready);$('stop').click();
  const latest=pause('latest.txt'),fresh=upload([file('latest.txt','Latest source'),file('latest-second.tsv','x\t1')]);await wait(latest.ready);older.resolve();await old;
  assert($('source-file').disabled&&project().sources.length===0,'older-completion-cannot-release-or-modify-newer-batch');latest.resolve();await fresh;
  assert(project().sources.map(s=>s.name).join('|')==='latest.txt|latest-second.tsv','newer-batch-finishes-with-all-its-files');
  assert(!JSON.stringify(NexusStudioUI.snapshot()).includes('Discarded source'),'cancelled-source-does-not-leak-into-history');
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,real_file_inputs_tested:true,network_requests:0,authority:'none'});
 }catch(error){$('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:error.message,checks})}
 finally{File.prototype.arrayBuffer=native}
});
"""

if __name__ == '__main__':
    module.main()
