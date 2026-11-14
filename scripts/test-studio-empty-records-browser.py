#!/usr/bin/env python3
"""Real Studio downloads preserve all-missing delimited records."""
import importlib.util
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('studio_browser', ROOT/'scripts/test-studio-browser.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.MIN_CHECKS = 20
module.WITNESS = r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[],assert=(v,k)=>{if(!v)throw Error(k);checks.push(k)};let stage='boot';
 const finish=report=>{$('nexus-browser-result').textContent=JSON.stringify(report)};
 const timer=setTimeout(()=>finish({status:'FAIL',reason:'empty-record-witness-timeout',stage,checks}),20000);
 window.addEventListener('error',()=>finish({status:'FAIL',reason:'empty-record-witness-script-error',stage,checks}));
 const fill=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const select=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('change'))};
 const downloads=[],blobs=new Map(),original=URL.createObjectURL;URL.createObjectURL=b=>{const u=original(b);blobs.set(u,b);return u};HTMLAnchorElement.prototype.click=function(){downloads.push(blobs.get(this.href))};
 const handle=$('data-run').onclick,tasks=[];$('data-run').onclick=event=>{const task=Promise.resolve(handle(event));tasks.push(task);return task};
 async function analyse(name,text){stage='analyse:'+name;const dt=new DataTransfer();dt.items.add(new File([text],name));$('data-file').files=dt.files;$('data-file').dispatchEvent(new Event('change'));$('data-run').click();await tasks.at(-1)}
 async function report(){stage='export';$('data-export').click();return JSON.parse(await downloads.at(-1).text())}
 try{
  window.confirm=()=>true;window.fetch=()=>{throw Error('unexpected-network')};fill('project-title','SYNTHETIC EMPTY RECORDS');$('new-project').click();
  for(const [kind,sep] of [['csv',','],['tsv','\t']]){
   const raw=`Group${sep}Value\r\nA${sep}1\r\n${sep}\r\n""${sep}""\r\nB${sep}3\r\n`;
   await analyse('empty-records.'+kind,raw);select('data-group','0');select('data-metric','1');const data=await report();
   assert(data.rows===4,kind+'-empty-records-retain-row-count');
   assert(data.column_stats.every(c=>c.missing===2),kind+'-missing-count-includes-empty-records');
   assert(data.column_stats[1].summary.count===2&&data.column_stats[1].summary.mean===2,kind+'-missing-records-do-not-become-numeric-zero');
   assert(data.groups.reduce((n,g)=>n+g.count,0)===4,kind+'-group-total-matches-all-records');
   const missing=data.groups.find(g=>g.missing);assert(missing.count===2&&missing.numeric_n===0&&missing.metric_mean===null,kind+'-missing-group-has-no-invented-metric');
   assert($('data-summary').textContent.includes('4 × 2')&&$('data-summary').textContent.includes('missing=2'),kind+'-missing-records-visible-in-summary');
   stage='raw-sha';const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(raw))),x=>x.toString(16).padStart(2,'0')).join('');assert(data.source.sha256===hash,kind+'-raw-provenance-unchanged');
   await analyse('only-missing.'+kind,'Value\n""\n');const only=await report();assert(only.rows===1&&only.column_stats[0].missing===1&&only.column_stats[0].summary===null,kind+'-single-empty-record-is-accepted');
   await analyse('blank-line.'+kind,'Value\n1\n\n3\n');const blank=await report();assert(blank.rows===3&&blank.column_stats[0].missing===1,kind+'-blank-physical-record-is-counted');
   await analyse('terminated.'+kind,'Value\n1\n3\n');assert((await report()).rows===2,kind+'-trailing-terminator-adds-no-record');
  }
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,real_files_and_crypto:true,network_requests:0,authority:'none'});
 }catch(error){finish({status:'FAIL',reason:error.message,stage,checks})}finally{clearTimeout(timer)}
});
"""
if __name__ == '__main__':
    module.main()
