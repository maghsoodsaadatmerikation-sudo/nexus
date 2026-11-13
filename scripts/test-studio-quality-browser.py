#!/usr/bin/env python3
"""Actual browser: integrated numerical analysis, guarded deletion, retrieval and chart pixels."""
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('studio_browser',ROOT/'scripts/test-studio-browser.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.MIN_CHECKS=20
module.WITNESS=r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[];const assert=(v,label)=>{if(!v)throw Error(label);checks.push(label)};
 const fill=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const select=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('change',{bubbles:true}))};
 const wait=async fn=>{for(let i=0;i<400;i++){if(fn())return;await new Promise(r=>setTimeout(r,15))}throw Error('wait-timeout')};
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));const snapshot=()=>NexusStudioUI.snapshot(),project=()=>snapshot().projects.find(p=>p.id===$('projects').value);
 window.confirm=()=>true;let network=0;window.fetch=()=>{network++;throw Error('network-disabled')};
 const downloads=[],blobs=new Map(),originalURL=URL.createObjectURL;URL.createObjectURL=blob=>{const url=originalURL(blob);blobs.set(url,blob);return url};HTMLAnchorElement.prototype.click=function(){downloads.push({name:this.download,blob:blobs.get(this.href)})};
 function inputFile(id,file){const dt=new DataTransfer();dt.items.add(file);$(id).files=dt.files;$(id).dispatchEvent(new Event('change'))}
 try{
  assert(document.querySelector('.tool-nav a[href="#data-card"]')&&$('capability-status').textContent.includes('not active'),'tool-navigation-and-honest-model-status');
  fill('project-title','QUALITY SYNTHETIC PROJECT');$('new-project').click();const pid=project().id;$('new-thread').click();fill('message','A question');$('message').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',ctrlKey:true,bubbles:true,cancelable:true}));assert(project().threads[0].nodes.length===2,'message-shortcut-runs-local-guide-without-network');
  const thread=project().threads[0];$('delete-thread').click();assert(project().threads.length===0&&!$('undo-removal').disabled,'chat-removal-offers-undo');$('undo-removal').click();assert(project().threads[0].id===thread.id&&project().threads[0].nodes.length===2,'undo-restores-entire-chat-graph');
  $('delete-project').click();assert(snapshot().projects.length===0,'project-removed');$('undo-removal').click();assert(project().id===pid,'undo-restores-selected-project');
  inputFile('source-file',new File(['The earth is round.\nArt is a craft.\nكیفیت يادگيری\n星空和月亮'],'reference.txt'));await wait(()=>project().sources.length===1);fill('source-query','art');$('search-sources').click();assert($('source-results').textContent.includes('reference.txt:2:1')&&!$('source-results').textContent.includes('earth'),'whole-word-search-avoids-substring-false-positive');fill('source-query','کیفیت');$('search-sources').click();assert($('source-results').textContent.includes('كیفیت'),'arabic-persian-keyboard-forms-normalized');
  $('source-list').querySelector('button').click();assert(!$('source-results').textContent,'removing-source-clears-stale-search-results');$('undo-removal').click();assert(project().sources.length===1,'source-removal-can-be-recovered');
  fill('document-title','Analysis draft');$('new-document').click();fill('editor','immutable original version');$('save-version').click();const docId=project().documents[0].id;$('delete-document').click();$('undo-removal').click();assert(project().documents[0].id===docId&&project().documents[0].versions[0].text==='immutable original version','document-removal-undo-preserves-versions');
  const csv='Group,Score,Cost\nA,1,10\nA,2,20\nB,3,30\nB,4,40\nB,,50\n';inputFile('data-file',new File([csv],'sample.csv'));$('data-run').click();await wait(()=>$('data-status').textContent.includes('Analysis ready'));assert($('data-summary').textContent.includes('5 × 3')&&$('data-summary').textContent.includes('mean=2.5'),'integrated-analysis-computes-real-descriptive-values');assert($('data-summary').textContent.includes('missing=1')&&$('data-summary').textContent.includes('r=1'),'missing-and-correlation-sample-visible');
  select('data-group','0');select('data-metric','1');assert($('data-summary').textContent.includes('B: n=3; mean=3.5'),'group-mean-is-pairwise-complete');$('data-chart').click();assert(!$('chart').hidden&&JSON.parse($('chart-json').value).values[0]===3.5,'analysis-result-flows-into-real-chart-tool');
  $('data-copy').click();assert($('editor').value.includes('mean=2.5')&&project().documents[0].versions.length===1,'analysis-copy-is-an-unsaved-canvas-draft');$('save-version').click();assert(project().documents[0].versions.length===2,'analysis-summary-saved-as-new-immutable-version');
  $('data-export').click();const report=JSON.parse(await downloads.at(-1).blob.text());assert(report.rows===5&&report.groups[0].metric_mean===3.5&&report.source.sha256.length===64&&!report.raw_rows,'exported-report-has-provenance-and-aggregated-values');
  fill('chart-json','{"type":"line","title":"One point","labels":["Only"],"values":[5]}');$('chart-draw').click();const pixel=$('chart').getContext('2d').getImageData(630,90,1,1).data;assert(pixel[1]>pixel[0]&&pixel[3]===255,'single-point-line-chart-has-a-visible-data-marker');
  const native=File.prototype.arrayBuffer;let resume;File.prototype.arrayBuffer=()=>new Promise(r=>resume=r);inputFile('data-file',new File(['x\n1\n'],'pending.csv'));$('data-run').click();await wait(()=>resume);$('lock').click();resume(new TextEncoder().encode('x\n1\n').buffer);await sleep(40);File.prototype.arrayBuffer=native;assert(!$('data-summary').textContent&&snapshot().projects.length===0&&$('undo-removal').disabled,'lock-clears-private-analysis-and-undo-and-rejects-late-results');
  $('language').value='fa';$('language').dispatchEvent(new Event('change'));assert($('data-card').textContent.includes('تحلیل یکپارچه')&&document.documentElement.dir==='rtl','integrated-quality-interface-in-persian');assert(document.documentElement.scrollWidth<=innerWidth+2,'integrated-tools-no-horizontal-overflow');assert(network===0,'all-integrated-analysis-and-recovery-work-with-zero-network');
  $('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,width:innerWidth,network_requests:network,real_model:false});
 }catch(e){$('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:e.message,checks})}
});
"""
if __name__=='__main__':module.main()
