  // Pilot 18: local-only, bounded, non-authoritative data analysis.
  // Kept inlined by build-ui-languages.py so the downloaded HTML remains standalone.
  const ANALYSIS_MAX_BYTES=NexusTable.MAX_BYTES,ANALYSIS_MAX_ROWS=NexusTable.MAX_ROWS,ANALYSIS_MAX_COLUMNS=NexusTable.MAX_COLUMNS;
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
  const {normalizedTable}=NexusTable;
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
    if(['json','csv','tsv'].includes(ext))return NexusTable.parse(text,ext);
    throw Error('unsupported-analysis');
  }
  const {strictNumeric,numberStats,histogram,analyseTable}=NexusTable;
  function metricFormat(value){
    if(value===null||value===undefined)return '—';
    return typeof value==='number'?new Intl.NumberFormat(interfaceLang,{maximumFractionDigits:4}).format(value):String(value);
  }
  function analysisBars(bars,total=null){
    const host=$('analysis-bars');host.replaceChildren();
    const shown=bars.slice(0,10);
    if(total!==null&&shown.length)host.append(part('small',t('m391')+': '+shown.length+'/'+total));
    const max=Math.max(1,...bars.map(x=>x.count));
    for(const item of shown){
      const wrap=part('div','','entry');
      wrap.append(part('small',item.label+' — '+metricFormat(item.count)));
      const track=part('div','','analysis-track'),bar=part('div','','analysis-bar');
      bar.style.width=(100*item.count/max).toFixed(2)+'%';track.append(bar);wrap.append(track);host.append(wrap);
    }
  }
  const {groupReport,GROUP_PREVIEW_LIMIT}=NexusTable;
  function renderAnalysisResults(){
    if(!analysisData)return;
    const {table,report}=analysisData,group=Number($('analysis-group').value),metric=Number($('analysis-metric').value);
    const grouping=groupReport(table,group,metric),groups=grouping.groups.slice(0,GROUP_PREVIEW_LIMIT);
    const lines=[t('m386')+': '+report.rows+' × '+report.columns,
      t('m387')+': '+report.source.name+' / SHA-256 '+report.source.sha256,''];
    for(const column of report.column_stats){
      const base=column.name+': '+t('m388')+' '+column.missing+'; '+t('m389')+' '+column.distinct;
      const s=column.summary;
      lines.push(s?base+'; n='+s.count+'; invalid='+column.invalid_numeric+'; mean='+metricFormat(s.mean)+'; median='+
        metricFormat(s.median)+'; SD='+metricFormat(s.sample_stddev)+'; min='+metricFormat(s.min)+'; max='+metricFormat(s.max):
        base+'; '+t('m390')+' '+column.top_values.map(x=>x.value+' ('+x.count+')').join(', '));
    }
    if(groups.length){lines.push('',t('m391')+': '+table.columns[group]+' ('+groups.length+'/'+grouping.group_count+')');
      for(const g of groups)lines.push(g.label+': n='+g.count+(metric>=0?'; mean='+metricFormat(g.metric_mean)+' (n='+g.numeric_n+')':''));}
    if(report.correlations.length){lines.push('',t('m392'));
      for(const pair of report.correlations.slice(0,12))
        lines.push(pair.left+' / '+pair.right+': r='+metricFormat(pair.pearson_r)+' (n='+pair.pairs+')');}
    lines.push('',t('m393'));
    $('analysis-summary').textContent=lines.join('\n');
    if(groups.length)analysisBars(groups,grouping.group_count);
    else if(metric>=0){
      const numbers=table.rows.map(r=>strictNumeric(r[metric])).filter(x=>x!==null);
      if(!numbers.length){analysisBars([]);return;}
      analysisBars(histogram(numbers));
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
    const report={...analysisData.report,...groupReport(analysisData.table,Number($('analysis-group').value),Number($('analysis-metric').value))};
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
