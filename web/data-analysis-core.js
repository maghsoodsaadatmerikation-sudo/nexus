  // Pilot 18: local-only, bounded, non-authoritative data analysis.
  // Kept inlined by build-ui-languages.py so the downloaded HTML remains standalone.
  const ANALYSIS_MAX_BYTES=1024*1024,ANALYSIS_MAX_ROWS=5000,ANALYSIS_MAX_COLUMNS=40;
  let analysisData=null,analysisContext=null,analysisJob=0;
  function analysisStatus(key){$('analysis-state').textContent=t(key);}
  function clearAnalysis(){
    analysisJob++;analysisData=null;analysisContext=null;
    $('analysis-run').disabled=false;
    $('analysis-summary').textContent='';$('analysis-bars').replaceChildren();
    $('analysis-group').replaceChildren();$('analysis-metric').replaceChildren();
    $('analysis-download').disabled=true;$('analysis-claim').disabled=true;
  }
  function refreshAnalysisSources(){
    const select=$('analysis-source'),selected=select.value;
    const candidates=fileTray.filter(f=>['csv','tsv','json','xlsx'].includes(f.name.split('.').pop().toLowerCase())&&f.size<=ANALYSIS_MAX_BYTES);
    select.replaceChildren();
    const intro=document.createElement('option');intro.value='';intro.textContent=t('m373');select.append(intro);
    for(const file of candidates){
      const o=document.createElement('option');o.value=file.id;o.textContent=file.name;select.append(o);
    }
    if(candidates.some(f=>f.id===selected))select.value=selected;
    if(analysisContext&&(analysisContext.epoch!==fileEpoch||
       analysisContext.workspace!==state.workspace||
       !fileTray.some(f=>f.id===analysisContext.id&&f.sha===analysisContext.sha))) {
      clearAnalysis();analysisStatus('m382');
    }
  }
  function parseDelimited(text,delimiter){
    if(text.length>ANALYSIS_MAX_BYTES)throw Error('text-budget');
    const rows=[],row=[];let value='',quoted=false,justClosed=false;
    const finishField=()=>{row.push(value);value='';justClosed=false;if(row.length>ANALYSIS_MAX_COLUMNS)throw Error('columns');};
    const finishRow=()=>{finishField();rows.push(row.splice(0));if(rows.length>ANALYSIS_MAX_ROWS+1)throw Error('rows');};
    for(let i=0;i<text.length;i++){
      const c=text[i];
      if(quoted){
        if(c==='"'){if(text[i+1]==='"'){value+='"';i++;}else{quoted=false;justClosed=true;}}
        else value+=c;
      }else if(c==='"'&&value===''&&!justClosed)quoted=true;
      else if(c===delimiter)finishField();
      else if(c==='\r'||c==='\n'){
        if(c==='\r'&&text[i+1]==='\n')i++;
        finishRow();
      }else if(justClosed)throw Error('csv-close');
      else if(c==='"')throw Error('csv-quote');
      else value+=c;
      if(value.length>ANALYSIS_MAX_BYTES)throw Error('field-size');
    }
    if(quoted)throw Error('csv-unclosed');
    if(value!==''||row.length||justClosed)finishRow();
    return rows;
  }
  function normalizedTable(header,body){
    if(!Array.isArray(header)||!header.length||header.length>ANALYSIS_MAX_COLUMNS||
       !Array.isArray(body)||!body.length||body.length>ANALYSIS_MAX_ROWS)throw Error('table-shape');
    const used=new Set();
    const columns=header.map((name,i)=>{
      let key=String(name??'').trim().slice(0,160)||('Column '+(i+1));
      const root=key;let suffix=2;
      while(used.has(key)){key=root+' ('+suffix+++')';}
      used.add(key);return key;
    });
    const rows=body.map(row=>{
      if(!Array.isArray(row)||row.length>columns.length)throw Error('row-width');
      return columns.map((_,j)=>{
        const value=row[j];
        if(value===null||value===undefined)return '';
        if(!['string','number','boolean'].includes(typeof value)||!Number.isFinite(value===true?1:value===false?0:typeof value==='number'?value:0))throw Error('non-scalar');
        const text=String(value);
        if(text.length>10000)throw Error('cell-length');
        return text;
      });
    });
    return {columns,rows};
  }
  function parseJsonTable(text){
    const data=JSON.parse(text);
    if(!Array.isArray(data)||data.length===0||data.length>ANALYSIS_MAX_ROWS)throw Error('json-array');
    const columns=[];
    for(const row of data){
      if(!row||typeof row!=='object'||Array.isArray(row))throw Error('json-object');
      for(const key of Object.keys(row)){
        if(key.length>160)throw Error('json-key');
        if(!columns.includes(key)){columns.push(key);if(columns.length>ANALYSIS_MAX_COLUMNS)throw Error('json-columns');}
      }
    }
    return normalizedTable(columns,data.map(row=>columns.map(key=>Object.hasOwn(row,key)?row[key]:null)));
  }
  async function parseXlsxTable(bytes){
    const zip=zipReader(bytes);
    const worksheets=zip.names.filter(n=>/^xl\/worksheets\/sheet\d+\.xml$/.test(n))
      .sort((a,b)=>a.localeCompare(b,undefined,{numeric:true}));
    if(!worksheets.length||worksheets.length>20)throw Error('sheets');
    let shared=[];
    if(zip.names.includes('xl/sharedStrings.xml')){
      shared=xmlElements(xmlDocument(await zip.read('xl/sharedStrings.xml')),'si')
        .map(si=>xmlText(si,'t'));
      if(shared.length>10000)throw Error('strings');
    }
    const sheet=xmlDocument(await zip.read(worksheets[0])),lines=[];
    let cellCount=0,previousRow=0;
    for(const row of xmlElements(sheet,'row')){
      const rowNumber=Number(row.getAttribute('r')||lines.length+1);
      if(!Number.isSafeInteger(rowNumber)||rowNumber<=previousRow||rowNumber>2001)throw Error('xlsx-row');
      previousRow=rowNumber;
      const cells=[];
      for(const cell of xmlElements(row,'c')){
        if(++cellCount>5000||xmlElements(cell,'f').length)throw Error('xlsx-formula');
        const ref=cell.getAttribute('r')||'';
        const match=/^([A-Z]{1,2})\d+$/.exec(ref);
        if(!match)throw Error('xlsx-cell');
        const col=Array.from(match[1]).reduce((n,c)=>n*26+c.charCodeAt(0)-64,0)-1;
        if(col>=ANALYSIS_MAX_COLUMNS||cells[col]!==undefined)throw Error('xlsx-width');
        let value='';
        const type=cell.getAttribute('t');
        if(type==='inlineStr')value=xmlText(cell,'t');
        else if(type==='s'){
          const raw=xmlText(cell,'v'),index=Number(raw);
          if(!/^\d+$/.test(raw)||!Number.isSafeInteger(index)||index>=shared.length)throw Error('xlsx-string');
          value=shared[index];
        }else if(type==='e')throw Error('xlsx-error-cell');
        else value=xmlText(cell,'v');
        cells[col]=value;
      }
      while(lines.length<rowNumber-1)lines.push([]);
      lines.push(cells);
    }
    return normalizedTable(lines[0]||[],lines.slice(1));
  }
  async function readAnalysisFile(item){
    if(item.size===0||item.size>ANALYSIS_MAX_BYTES)throw Error('analysis-budget');
    const bytes=new Uint8Array(await item.blob.arrayBuffer());
    if(bytes.length!==item.size||await fileHash(bytes)!==item.sha)throw Error('hash');
    const ext=item.name.split('.').pop().toLowerCase();
    if(ext==='xlsx')return parseXlsxTable(bytes);
    const text=decodeFileText(bytes).replace(/^\uFEFF/,'');
    if(ext==='json')return parseJsonTable(text);
    if(ext==='csv'||ext==='tsv'){
      const sep=ext==='tsv'?'\t':',';
      const rows=parseDelimited(text,sep);
      return normalizedTable(rows[0]||[],rows.slice(1).filter(row=>row.some(x=>x!=='')));
    }
    throw Error('unsupported-analysis');
  }
  const strictNumeric=value=>{
    const s=String(value).trim();
    if(!/^[+-]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[Ee][+-]?\d+)?$/.test(s))return null;
    const n=Number(s);return Number.isFinite(n)?n:null;
  };
  function numberStats(values){
    const nums=values.slice().sort((a,b)=>a-b),n=nums.length;
    if(!n)return null;
    let mean=0,m2=0;
    values.forEach((x,i)=>{const d=x-mean;mean+=d/(i+1);m2+=d*(x-mean);});
    const quantile=q=>{const p=(n-1)*q,lo=Math.floor(p),hi=Math.ceil(p);return nums[lo]+(nums[hi]-nums[lo])*(p-lo);};
    const value=x=>Number.isFinite(x)?x:null;
    return {count:n,min:value(nums[0]),max:value(nums[n-1]),mean:value(mean),median:value(quantile(.5)),
      q1:value(quantile(.25)),q3:value(quantile(.75)),sample_stddev:n>1?value(Math.sqrt(m2/(n-1))):null};
  }
  function analyseTable(table,source){
    const {columns,rows}=table,stats=[],numeric=[];
    columns.forEach((name,i)=>{
      const values=rows.map(r=>r[i]),missing=values.filter(x=>!String(x).trim()).length;
      const parsed=values.map(strictNumeric).filter(x=>x!==null);
      const validNonMissing=rows.length-missing,asNumeric=parsed.length>0&&parsed.length/validNonMissing>=.8;
      const frequencies=new Map();
      for(const value of values){const key=String(value).trim()||'(missing)';frequencies.set(key,(frequencies.get(key)||0)+1);}
      const common=Array.from(frequencies,([value,count])=>({value,count}))
        .sort((a,b)=>b.count-a.count||a.value.localeCompare(b.value)).slice(0,5);
      stats.push({name,missing,distinct:frequencies.size,type:asNumeric?'numeric':'categorical',
        numeric_count:parsed.length,invalid_numeric:asNumeric?validNonMissing-parsed.length:0,
        summary:asNumeric?numberStats(parsed):null,top_values:common});
      if(asNumeric)numeric.push(i);
    });
    const correlations=[];
    for(let i=0;i<numeric.length;i++)for(let j=i+1;j<numeric.length;j++){
      const a=numeric[i],b=numeric[j],pairs=rows.map(r=>[strictNumeric(r[a]),strictNumeric(r[b])])
        .filter(([x,y])=>x!==null&&y!==null);
      if(pairs.length<3)continue;
      const mx=pairs.reduce((sum,p)=>sum+p[0],0)/pairs.length,my=pairs.reduce((sum,p)=>sum+p[1],0)/pairs.length;
      let cov=0,vx=0,vy=0;
      for(const [x,y] of pairs){const dx=x-mx,dy=y-my;cov+=dx*dy;vx+=dx*dx;vy+=dy*dy;}
      const r=vx>0&&vy>0?cov/Math.sqrt(vx*vy):null;
      correlations.push({left:columns[a],right:columns[b],pairs:pairs.length,pearson_r:r===null?null:Math.max(-1,Math.min(1,r))});
    }
    return {schema:'nexus.local-analysis.v1',authority:'none',source:{name:source.name,sha256:source.sha,
      bytes:source.size,verification:'byte-identity-only'},limits:{max_rows:ANALYSIS_MAX_ROWS,max_columns:ANALYSIS_MAX_COLUMNS},
      rows:rows.length,columns:columns.length,column_stats:stats,correlations,notes:[
      'Exploratory descriptive analysis only; no causal inference, diagnosis, prediction or human judgment.',
      'Values are not independently verified; missing, invalid and mixed columns can affect statistics.',
      'Numeric parsing uses dot decimals and sample standard deviation; Pearson uses pairwise complete cases.']};
  }
  function metricFormat(value){
    if(value===null||value===undefined)return '—';
    return typeof value==='number'?new Intl.NumberFormat(interfaceLang,{maximumFractionDigits:4}).format(value):String(value);
  }
  function analysisBars(bars){
    const host=$('analysis-bars');host.replaceChildren();
    const max=Math.max(1,...bars.map(x=>x.count));
    for(const item of bars.slice(0,10)){
      const wrap=part('div','','entry');
      wrap.append(part('small',item.label+' — '+metricFormat(item.count)));
      const track=part('div','','analysis-track'),bar=part('div','','analysis-bar');
      bar.style.width=(100*item.count/max).toFixed(2)+'%';track.append(bar);wrap.append(track);host.append(wrap);
    }
  }
  function analysisGroups(table,index,metric){
    if(index<0)return [];
    const groups=new Map();
    for(const row of table.rows){
      const label=String(row[index]).trim()||'(missing)';
      if(!groups.has(label))groups.set(label,{label,count:0,values:[]});
      const item=groups.get(label);item.count++;
      if(metric>=0){const v=strictNumeric(row[metric]);if(v!==null)item.values.push(v);}
    }
    return Array.from(groups.values()).map(g=>({label:g.label,count:g.count,
      metric_mean:metric<0?null:numberStats(g.values)?.mean??null,numeric_n:g.values.length}))
      .sort((a,b)=>b.count-a.count||a.label.localeCompare(b.label)).slice(0,12);
  }
  function renderAnalysisResults(){
    if(!analysisData)return;
    const {table,report}=analysisData,group=Number($('analysis-group').value),metric=Number($('analysis-metric').value);
    const groups=analysisGroups(table,group,metric);
    const lines=[t('m386')+': '+report.rows+' × '+report.columns,
      t('m387')+': '+report.source.name+' / SHA-256 '+report.source.sha256,''];
    for(const column of report.column_stats){
      const base=column.name+': '+t('m388')+' '+column.missing+'; '+t('m389')+' '+column.distinct;
      const s=column.summary;
      lines.push(s?base+'; n='+s.count+'; mean='+metricFormat(s.mean)+'; median='+
        metricFormat(s.median)+'; SD='+metricFormat(s.sample_stddev)+'; min='+metricFormat(s.min)+'; max='+metricFormat(s.max):
        base+'; '+t('m390')+' '+column.top_values.map(x=>x.value+' ('+x.count+')').join(', '));
    }
    if(groups.length){lines.push('',t('m391')+': '+table.columns[group]);
      for(const g of groups)lines.push(g.label+': n='+g.count+(metric>=0?'; mean='+metricFormat(g.metric_mean)+' (n='+g.numeric_n+')':''));}
    if(report.correlations.length){lines.push('',t('m392'));
      for(const pair of report.correlations.slice(0,12))
        lines.push(pair.left+' / '+pair.right+': r='+metricFormat(pair.pearson_r)+' (n='+pair.pairs+')');}
    lines.push('',t('m393'));
    $('analysis-summary').textContent=lines.join('\n');
    if(groups.length)analysisBars(groups);
    else if(metric>=0){
      const numbers=table.rows.map(r=>strictNumeric(r[metric])).filter(x=>x!==null);
      if(!numbers.length){analysisBars([]);return;}
      const lo=Math.min(...numbers),hi=Math.max(...numbers),buckets=Array.from({length:8},(_,i)=>({label:String(i+1),count:0}));
      for(const n of numbers)buckets[hi===lo?0:Math.min(7,Math.floor((n-lo)/(hi-lo)*8))].count++;
      analysisBars(buckets);
    }else analysisBars([]);
  }
  $('analysis-source').addEventListener('change',()=>{clearAnalysis();analysisStatus('m383');});
  $('analysis-group').addEventListener('change',renderAnalysisResults);
  $('analysis-metric').addEventListener('change',renderAnalysisResults);
  $('analysis-run').addEventListener('click',async()=>{
    const item=fileTray.find(x=>x.id===$('analysis-source').value);
    if(!item||fileBusy){analysisStatus('m374');return;}
    const epoch=fileEpoch,workspace=state.workspace,job=++analysisJob;
    clearAnalysis();analysisJob=job;
    $('analysis-run').disabled=true;analysisStatus('m375');
    try{
      const table=await readAnalysisFile(item);
      if(job!==analysisJob||epoch!==fileEpoch||workspace!==state.workspace||
        !fileTray.some(x=>x.id===item.id&&x.sha===item.sha))return;
      const report=analyseTable(table,item);
      analysisData={table,report};analysisContext={id:item.id,sha:item.sha,epoch,workspace};
      const group=$('analysis-group'),metric=$('analysis-metric');
      group.replaceChildren();metric.replaceChildren();
      const noneGroup=document.createElement('option');noneGroup.value='-1';noneGroup.textContent=t('m378');group.append(noneGroup);
      const noneMetric=document.createElement('option');noneMetric.value='-1';noneMetric.textContent=t('m379');metric.append(noneMetric);
      table.columns.forEach((name,i)=>{
        const option=document.createElement('option');option.value=String(i);option.textContent=name;group.append(option);
        if(report.column_stats[i].type==='numeric'){
          const o=document.createElement('option');o.value=String(i);o.textContent=name;metric.append(o);
        }
      });
      metric.value=metric.options.length>1?metric.options[1].value:'-1';
      renderAnalysisResults();$('analysis-download').disabled=false;$('analysis-claim').disabled=false;
      analysisStatus('m376');
    }catch{if(job===analysisJob){clearAnalysis();analysisStatus('m377');}}
    finally{if(job===analysisJob)$('analysis-run').disabled=false;}
  });
  $('analysis-download').addEventListener('click',()=>{
    if(!analysisData||!analysisContext||analysisContext.epoch!==fileEpoch||
       analysisContext.workspace!==state.workspace)return clearAnalysis();
    if(!window.confirm(t('m394')))return;
    const report={...analysisData.report,group_by:$('analysis-group').value==='-1'?null:
      analysisData.table.columns[Number($('analysis-group').value)],
      groups:analysisGroups(analysisData.table,Number($('analysis-group').value),Number($('analysis-metric').value))};
    downloadFileBlob(new Blob([JSON.stringify(report,null,2)+'\n'],{type:'application/json;charset=utf-8'}),
      'nexus-analysis-'+analysisContext.sha.slice(0,12)+'.json');
    analysisStatus('m395');
  });
  $('analysis-claim').addEventListener('click',()=>{
    if(!analysisData||!analysisContext||analysisContext.epoch!==fileEpoch||
       analysisContext.workspace!==state.workspace)return clearAnalysis();
    if(($('claim').value.trim()||$('source').value.trim())&&!window.confirm(t('m344')))return;
    const report=analysisData.report;
    const brief=report.column_stats.filter(c=>c.summary).slice(0,4).map(c=>c.name+
      ' n='+c.summary.count+' mean='+metricFormat(c.summary.mean)+' median='+metricFormat(c.summary.median)).join('; ');
    const value=('Descriptive analysis; '+report.rows+' rows / '+report.columns+' columns. '+brief+
      '. Observations are unverified, non-causal and require human review.').slice(0,2000);
    $('claim').value=value;$('source').value='local-analysis:sha256:'+report.source.sha256;
    $('origin').value='machine_analysis';$('uncertainty').value='unknown';
    for(const id of ['claim','source'])$(id).dispatchEvent(new Event('input',{bubbles:true}));
    $('claim').focus();analysisStatus('m396');
  });
