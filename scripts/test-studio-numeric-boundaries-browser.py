#!/usr/bin/env python3
"""Real Studio downloads preserve integer identity and reject numeric underflow."""
import importlib.util
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('studio_browser', ROOT/'scripts/test-studio-browser.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.MIN_CHECKS = 12
module.WITNESS = r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[],assert=(v,k)=>{if(!v)throw Error(k);checks.push(k)};
 const fill=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const select=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('change'))};
 const downloads=[],blobs=new Map(),original=URL.createObjectURL;URL.createObjectURL=b=>{const u=original(b);blobs.set(u,b);return u};HTMLAnchorElement.prototype.click=function(){downloads.push(blobs.get(this.href))};
 const handle=$('data-run').onclick,tasks=[];$('data-run').onclick=event=>{const task=Promise.resolve(handle(event));tasks.push(task);return task};
 async function analyse(name,text){const dt=new DataTransfer();dt.items.add(new File([text],name));$('data-file').files=dt.files;$('data-file').dispatchEvent(new Event('change'));$('data-run').click();await tasks.at(-1)}
 async function report(){$('data-export').click();return JSON.parse(await downloads.at(-1).text())}
 try{
  window.confirm=()=>true;window.fetch=()=>{throw Error('unexpected-network')};fill('project-title','SYNTHETIC NUMERIC BOUNDARIES');$('new-project').click();
  const raw='[{"id":9007199254740992},{"id":9007199254740993}]';await analyse('identifiers.json',raw);select('data-group','0');const ids=await report();
  assert(ids.groups.length===2,'large-json-identifiers-remain-two-distinct-groups');
  assert(ids.groups.some(g=>g.label==='9007199254740993'),'rounded-json-identifier-is-preserved-exactly');
  assert(ids.column_stats[0].type==='categorical'&&ids.column_stats[0].distinct===2,'unsafe-integer-identifiers-are-not-measurements');
  const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(raw))),x=>x.toString(16).padStart(2,'0')).join('');assert(ids.source.sha256===hash,'raw-input-provenance-is-unchanged');
  await analyse('tiny.csv','v\n5e-324\n5e-324\n');const tiny=(await report()).column_stats[0].summary;
  assert(tiny.median===Number.MIN_VALUE&&tiny.q1===Number.MIN_VALUE&&tiny.q3===Number.MIN_VALUE,'subnormal-percentiles-do-not-become-zero');assert($('data-summary').textContent.includes('median=5e-324'),'subnormal-median-is-visible');
  await analyse('underflow.json','[{"v":1},{"v":2},{"v":3},{"v":4},{"v":1e-400}]');const mixed=(await report()).column_stats[0];
  assert(mixed.summary.count===4&&mixed.summary.mean===2.5,'underflow-does-not-lower-the-mean-as-a-fake-zero');assert(mixed.invalid_numeric===1&&mixed.summary.min===1,'excluded-underflow-is-counted');assert($('data-summary').textContent.includes('invalid=1'),'excluded-input-is-visible-in-summary');
  await analyse('equivalent.json','[{"v":1},{"v":1.0},{"v":1e0}]');select('data-group','0');const equivalent=await report();assert(equivalent.group_count===1&&equivalent.groups[0].count===3,'ordinary-equivalent-json-numbers-still-group-together');
  await analyse('large.json','[{"v":1e307},{"v":2e307},{"v":3e307}]');const large=(await report()).column_stats[0];assert(large.type==='numeric'&&large.summary.count===3,'large-scientific-measurements-remain-supported');
  await analyse('invalid.json','[{1:2}]');assert(!$('data-summary').textContent&&$('data-export').disabled,'number-preservation-cannot-accept-invalid-json-keys');
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,real_files_and_crypto:true,network_requests:0,authority:'none'});
 }catch(error){$('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:error.message,checks})}
});
"""
if __name__ == '__main__':
    module.main()
