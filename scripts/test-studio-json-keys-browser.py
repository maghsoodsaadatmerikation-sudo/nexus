#!/usr/bin/env python3
"""Studio rejects duplicate decoded JSON keys and clears stale outputs."""
import importlib.util
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('studio_browser', ROOT/'scripts/test-studio-browser.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.MIN_CHECKS = 22
module.WITNESS = r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[],assert=(v,k)=>{if(!v)throw Error(k);checks.push(k)};let stage='boot';
 const finish=report=>{$('nexus-browser-result').textContent=JSON.stringify(report)};
 const timer=setTimeout(()=>finish({status:'FAIL',reason:'json-key-witness-timeout',stage,checks}),20000);
 window.addEventListener('error',()=>finish({status:'FAIL',reason:'json-key-witness-script-error',stage,checks}));
 const fill=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const select=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('change'))};
 const downloads=[],blobs=new Map(),original=URL.createObjectURL;URL.createObjectURL=b=>{const u=original(b);blobs.set(u,b);return u};HTMLAnchorElement.prototype.click=function(){downloads.push(blobs.get(this.href))};
 const handle=$('data-run').onclick,tasks=[];$('data-run').onclick=event=>{const task=Promise.resolve(handle(event));tasks.push(task);return task};
 async function analyse(name,text){stage='analyse:'+name;const dt=new DataTransfer();dt.items.add(new File([text],name));$('data-file').files=dt.files;$('data-file').dispatchEvent(new Event('change'));$('data-run').click();await tasks.at(-1)}
 async function report(){stage='export';$('data-export').click();return JSON.parse(await downloads.at(-1).text())}
 try{
  window.confirm=()=>true;window.fetch=()=>{throw Error('unexpected-network')};fill('project-title','SYNTHETIC JSON FIELDS');$('new-project').click();
  const good='[{"Score":1},{"Score":3}]',cases=[
   ['plain','[{"Score":1,"Score":99}]'],
   ['escaped','[{"Score":1,"\\u0053core":99}]'],
   ['proto','[{"__proto__":"first","__proto__":"second"}]'],
   ['shadowed','[{"Score":{"nested":1},"Score":99}]']
  ];
  for(const [label,raw] of cases){
   await analyse('good.json',good);assert($('data-summary').textContent.includes('2 × 1')&&!$('data-export').disabled,label+'-starts-with-valid-analysis');
   await analyse(label+'.json',raw);assert(!$('data-summary').textContent&&$('data-export').disabled&&$('data-copy').disabled&&$('data-chart').disabled,label+'-duplicate-clears-previous-analysis-and-actions');
   assert($('data-status').textContent.includes('duplicate JSON field names'),label+'-duplicate-error-is-actionable');
   const count=downloads.length;$('data-export').click();assert(downloads.length===count,label+'-duplicate-cannot-export-stale-result');
  }
  const escaped='[{"Score":1},{"\\u0053core":3}]';await analyse('valid-escaped.json',escaped);const valid=await report();assert(valid.rows===2&&valid.columns===1&&valid.column_stats[0].summary.mean===2,'same-decoded-key-in-different-rows-remains-valid');
  const text='[{"text":"{\\\"a\\\":1,\\\"a\\\":2}","Score":3}]';await analyse('inert-text.json',text);const inert=await report();assert(inert.column_stats[0].top_values[0].value==='{"a":1,"a":2}','duplicate-looking-text-remains-inert-string-data');
  select('language','fa');await analyse('persian-error.json',cases[0][1]);assert($('data-status').textContent.includes('تکراری'),'persian-duplicate-error-explains-correction');assert(!$('data-summary').textContent&&$('data-export').disabled,'translated-error-retains-fail-closed-state');
  select('language','en');await analyse('recovered.json',good);const recovered=await report();assert(recovered.column_stats[0].summary.mean===2,'valid-input-recovers-after-rejection');
  stage='raw-sha';const sha=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(good))),n=>n.toString(16).padStart(2,'0')).join('');assert(recovered.source.sha256===sha,'accepted-input-retains-original-byte-provenance');
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,real_files_and_crypto:true,network_requests:0,authority:'none'});
 }catch(error){finish({status:'FAIL',reason:error.message,stage,checks})}finally{clearTimeout(timer)}
});
"""
if __name__ == '__main__':
    module.main()
