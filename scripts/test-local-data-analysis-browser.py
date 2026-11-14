#!/usr/bin/env python3
"""Pilot 18: real, disposable browser tests of private bounded numerical analysis."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

WITNESS = r"""
window.addEventListener('load',async()=>{
 const $=id=>document.getElementById(id),checks=[];
 const assert=(ok,label)=>{if(!ok)throw Error(label);checks.push(label)};
 const sleep=()=>new Promise(r=>setTimeout(r,25));
 const wait=async fn=>{for(let i=0;i<420;i++){if(fn())return;await sleep()}throw Error('analysis-timeout')};
 const fill=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('input',{bubbles:true}))};
 const select=(id,value)=>{$(id).value=value;$(id).dispatchEvent(new Event('change',{bubbles:true}))};
 const submit=id=>$(id).dispatchEvent(new Event('submit',{cancelable:true,bubbles:true}));
 let allowed=true,network=0,downloads=[];
 window.fetch=()=>{network++;throw Error('network-forbidden')};
 window.confirm=()=>allowed;
 const original=URL.createObjectURL,blobs=new Map();
 URL.createObjectURL=b=>{const u=original(b);blobs.set(u,b);return u};
 HTMLAnchorElement.prototype.click=function(){downloads.push({name:this.download,blob:blobs.get(this.href)})};
 const add=async files=>{
  const dt=new DataTransfer();for(const f of files)dt.items.add(f);
  $('files-input').files=dt.files;$('files-input').dispatchEvent(new Event('change'));
  await wait(()=>$('files-input').value===''&&!$('files-add').disabled);
 };
 const pick=name=>{
  const opt=Array.from($('analysis-source').options).find(o=>o.textContent===name);
  if(!opt)throw Error('missing-source-option');
  select('analysis-source',opt.value);
 };
 const run=async success=>{
  $('analysis-run').click();
  await wait(()=>$('analysis-state').textContent.includes(success?'Analysis ready':'Analysis unavailable'));
 };
 const snapshot=async()=>{
  const n=downloads.length;$('export').click();assert(downloads.length===n+1,'workspace-export-remains-accessible');
  return await downloads.at(-1).blob.text();
 };
 try{
  assert(document.documentElement.lang==='en'&&$('analysis-panel')&&
    $('analysis-summary')&&$('analysis-bars'),'english-first-analysis-panel-exists');
  $('analysis-run').click();
  assert($('analysis-state').textContent.includes('Select a supported file'),'no-file-does-not-analyse');
  const csv='Label,Group,Score,Cost\nalice,A,1,10\nbob,A,2,20\ncarol,B,3,30\ndave,B,4,40\neve,B,,50\n';
  await add([new File([csv],'test-data.csv',{type:'text/csv'}),
             new File(['<scr'+'ipt>alert(1)</scr'+'ipt>'],'binary.png',{type:'image/png'})]);
  assert($('analysis-source').options.length===2,'only-supported-data-sources-appear');
  assert($('audit').textContent.includes('No events')||$('audit').textContent.length<90,
    'file-admission-does-not-create-audit-claim');
  pick('test-data.csv');await run(true);
  assert($('analysis-summary').textContent.includes('5 × 4'),'csv-row-and-column-count');
  assert($('analysis-summary').textContent.includes('Score')&&$('analysis-summary').textContent.includes('mean=2.5'),'descriptive-mean-median');
  assert($('analysis-summary').textContent.includes('Missing 1'),'missing-value-count-visible');
  assert($('analysis-summary').textContent.includes('r=1'),'pairwise-perfect-pearson-is-descriptive');
  assert(!document.querySelector('#analysis-summary img,#analysis-bars script'),'no-active-content-rendering');
  assert($('analysis-bars').querySelectorAll('.analysis-track').length===8,'numeric-histogram-is-visible');
  select('analysis-group','1');
  assert($('analysis-summary').textContent.includes('Group comparison')&&
    $('analysis-bars').querySelectorAll('.analysis-track').length===2,'grouping-breakdown-on-user-action');
  assert($('analysis-summary').textContent.includes('B: n=3'),'subgroup-counts-preserved');
  allowed=false;const cancelled=downloads.length;$('analysis-download').click();
  assert(downloads.length===cancelled,'unencrypted-analysis-export-requires-consent');
  allowed=true;$('analysis-download').click();
  const output=downloads.at(-1);const report=JSON.parse(await output.blob.text());
  assert(output.name.endsWith('.json')&&report.schema==='nexus.local-analysis.v1'&&
    report.authority==='none'&&report.rows===5,'downloaded-analysis-is-structured-json');
  const score=report.column_stats.find(c=>c.name==='Score');
  assert(score.summary.count===4&&score.summary.mean===2.5&&
    score.summary.median===2.5&&Math.abs(score.summary.sample_stddev-1.290994)<.00001,
    'independent-numeric-fixture-values');
  assert(report.groups.length===2&&report.groups[0].count===3&&
    report.groups[0].numeric_n===2&&report.groups[0].metric_mean===3.5,
    'group-mean-uses-nonmissing-numeric-cases');
  assert(report.correlations.some(c=>c.pearson_r===1&&c.pairs===4),
    'pairwise-correlation-sample-count');
  assert(!Object.hasOwn(report,'raw_rows')&&!Object.hasOwn(report,'workspace')&&
    !Object.hasOwn(report,'judgment'),'analysis-output-is-aggregated-not-full-workspace');
  const many='Group,Value\n'+Array.from({length:14},(_,i)=>'G'+String(i).padStart(2,'0')+','+i).join('\n');
  await add([new File([many],'many-groups.csv',{type:'text/csv'})]);pick('many-groups.csv');await run(true);
  select('analysis-group','0');select('analysis-metric','1');
  assert($('analysis-summary').textContent.includes('12/14')&&$('analysis-bars').querySelectorAll('.analysis-track').length===10&&$('analysis-bars').textContent.includes('10/14'),'offline-group-preview-discloses-coverage');
  $('analysis-download').click();const allGroups=JSON.parse(await downloads.at(-1).blob.text());
  assert(allGroups.groups.length===14&&allGroups.group_count===14&&allGroups.groups_complete===true,'offline-json-export-retains-all-groups');
  assert(allGroups.metric==='Value'&&allGroups.group_by==='Group'&&allGroups.groups.reduce((n,g)=>n+g.count,0)===14,'offline-group-export-identifies-metric-and-all-row-counts');
  select('ui-language','fa');
  assert(document.documentElement.dir==='rtl'&&$('analysis-title').textContent==='تحلیل محلی داده‌ها'&&
    $('analysis-summary').textContent.includes('ردیف × ستون'),'persian-analytics-without-recomputing-private-values');
  select('ui-language','en');
  $('analysis-claim').click();
  assert($('origin').value==='machine_analysis'&&$('uncertainty').value==='unknown'&&
    $('source').value.startsWith('local-analysis:sha256:')&&
    $('claims').textContent.includes('No evidence'),'summary-is-only-an-unregistered-machine-analysis-draft');
  assert(!$('draft-notice').hidden,'unregistered-summary-is-protected-as-draft');
  const json='[{"Group":"A","Score":2},{"Group":"B","Score":4},{"Group":"B","Score":null}]';
  await add([new File([json],'rows.json',{type:'application/json'})]);
  assert($('analysis-summary').textContent===''&&$('analysis-download').disabled,
    'new-file-admission-invalidates-prior-analysis');
  pick('rows.json');await run(true);
  assert($('analysis-summary').textContent.includes('3 × 2'),'json-array-of-flat-objects-supported');
  await add([new File(['[{"a":{"nested":7}}]'],'nested.json',{type:'application/json'})]);
  pick('nested.json');await run(false);
  assert($('analysis-download').disabled&&$('analysis-summary').textContent===''&&
    !$('claims').textContent.includes('Analysis ready'),'nested-json-is-rejected-without-claim');
  const tsv='Category\tAmount\n"tag\tcell"\t5\nother\t7\n';
  await add([new File([tsv],'rows.tsv',{type:'text/tab-separated-values'})]);
  pick('rows.tsv');await run(true);
  assert($('analysis-summary').textContent.includes('2 × 2')&&
    $('analysis-summary').textContent.includes('mean=6'),'quoted-tsv-and-numbers');
  const over=JSON.stringify(Array.from({length:5001},(_,i)=>({x:i})));
  await add([new File([over],'over.json',{type:'application/json'})]);
  pick('over.json');await run(false);
  assert($('analysis-summary').textContent===''&&$('analysis-download').disabled,
    'over-limit-dataset-fails-closed');
  fill('question','Synthetic numeric example');submit('ask-form');
  const before=await snapshot();
  select('files-format','xlsx');$('files-generate').click();
  await wait(()=>downloads.at(-1)?.name.endsWith('.xlsx'));
  const realExcel=downloads.at(-1).blob;
  await add([new File([await realExcel.arrayBuffer()],'generated.xlsx',{
    type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})]);
  pick('generated.xlsx');await run(true);
  assert($('analysis-summary').textContent.includes('× 5')&&
    $('analysis-summary').textContent.includes('Column')===false,
    'real-generated-office-xml-can-be-analysed');
  const after=await snapshot();
  assert(before===after,'analysis-does-not-change-committed-workspace-or-audit');
  const origBuffer=Blob.prototype.arrayBuffer;let release,held=false;
  Blob.prototype.arrayBuffer=async function(){if(!held){held=true;await new Promise(r=>release=r)}return origBuffer.call(this)};
  pick('test-data.csv');$('analysis-run').click();await wait(()=>!!release);
  $('new').click();release();await wait(()=>$('analysis-source').options.length===1);
  Blob.prototype.arrayBuffer=origBuffer;await sleep();
  assert($('analysis-summary').textContent===''&&$('analysis-download').disabled,
    'late-analysis-result-cannot-enter-replaced-workspace');
  assert($('analysis-source').options.length===1&&$('files-list').textContent.includes('No files'),
    'workspace-replacement-clears-file-and-data-memory');
  assert(network===0&&localStorage.length===0,'no-data-network-or-plaintext-browser-storage');
  $('nexus-browser-result').textContent=JSON.stringify({
    status:'PASS',checks,width:innerWidth,network_requests:network,authority:'none',
    real_user_tested:false,production_mutation:false,source_rows_exported:false});
 }catch(e){$('nexus-browser-result').textContent=JSON.stringify({
    status:'FAIL',reason:String(e.message).replace(/[^a-z0-9-_]/gi,'')})}
});
"""

def main():
    root=Path(__file__).resolve().parents[1]
    html=(root/'web/offline-pilot.html').read_text(encoding='utf8')
    assert 'NEXUS_DATA_ANALYSIS_BEGIN' in html and "connect-src 'none'" in html
    browser=next((shutil.which(n) for n in ('google-chrome','google-chrome-stable','chromium')
                  if shutil.which(n)),None)
    if browser is None:raise RuntimeError('real-browser-required')
    page_html=html.replace('</body>','<pre id="nexus-browser-result" hidden></pre><script>'+WITNESS+'</script></body>')
    reports=[]
    with tempfile.TemporaryDirectory(prefix='nexus-analysis-') as td:
        page=Path(td)/'index.html';page.write_text(page_html,encoding='utf8')
        for layout,dim in [('narrow','500,980'),('wide','1280,980')]:
            cmd=['node',str(root/'scripts/workspace-browser-runner.mjs'),
                 browser,page.as_uri(),str(Path(td)/layout),dim,'60000','30000']
            result=subprocess.run(cmd,capture_output=True,text=True,timeout=170)
            if result.returncode:
                import re
                match=re.search(r'"stage":"([a-z-]+)"',result.stderr)
                stage=match.group(1) if match else 'startup'
                raise RuntimeError('real-browser-runner-failed-'+stage)
            report=json.loads(result.stdout)
            if report.get('status')!='PASS' or len(report.get('checks',[]))<25:
                raise RuntimeError('analysis-browser-rejected: '+str(report.get('reason','checks')))
            assert (layout=='narrow')==(report['width']<=760)
            assert report['network_requests']==0 and report['authority']=='none'
            reports.append({'layout':layout,**report})
    print(json.dumps({'schema':'nexus.pilot-18.local-analysis-witness.v1',
                      'status':'PASS','reports':reports,'authority':'none'}))

if __name__=='__main__':main()
