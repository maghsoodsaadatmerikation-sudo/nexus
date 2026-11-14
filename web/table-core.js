/* Shared bounded descriptive table engine; no DOM, execution or network. */
(function(root){'use strict';
const ANALYSIS_MAX_BYTES=1024*1024,ANALYSIS_MAX_ROWS=5000,ANALYSIS_MAX_COLUMNS=40;
const GROUP_PREVIEW_LIMIT=12;
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
      const root=key.slice(0,150);let suffix=2;
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
    let data=JSON.parse(text);
    if(!Array.isArray(data)||data.length===0||data.length>ANALYSIS_MAX_ROWS)throw Error('json-array');
    const columns=[];
    for(const row of data){
      if(!row||typeof row!=='object'||Array.isArray(row))throw Error('json-object');
      for(const key of Object.keys(row)){
        if(key.length>160)throw Error('json-key');
        if(!columns.includes(key)){columns.push(key);if(columns.length>ANALYSIS_MAX_COLUMNS)throw Error('json-columns');}
      }
    }
    // Syntax is validated above before rewriting numeric value tokens. Quoted
    // strings (including object keys and escapes) are copied without alteration.
    const exact=text.replace(/"(?:\\[\s\S]|[^"\\])*"|-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/g,token=>{
      if(token[0]==='"')return token;
      const n=Number(token);if(!Number.isFinite(n))throw Error('non-scalar');
      let value=String(n);
      if(/^-?\d+$/.test(token)&&!Number.isSafeInteger(n))value=token;
      else if(n===0&&/[1-9]/.test(token.split(/[eE]/)[0]))value=token;
      else if(Number.isInteger(n)&&!Number.isSafeInteger(n))value=n.toExponential();
      return JSON.stringify(value);
    });
    data=JSON.parse(exact);
    return normalizedTable(columns,data.map(row=>columns.map(key=>Object.hasOwn(row,key)?row[key]:null)));
  }
  const strictNumeric=value=>{
    const s=String(value).trim().replace(/[۰-۹]/g,c=>String(c.charCodeAt(0)-1776)).replace(/[٠-٩]/g,c=>String(c.charCodeAt(0)-1632)).replace(/٫/g,'.');
    if(!/^[+-]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[Ee][+-]?\d+)?$/.test(s))return null;
    const n=Number(s);
    if(n===0&&/[1-9]/.test(s.split(/[Ee]/)[0]))return null;
    return Number.isFinite(n)&&!(/^[+-]?\d+$/.test(s)&&!Number.isSafeInteger(n))?n:null;
  };
  function numberStats(values){
    if(!Array.isArray(values)||values.some(x=>typeof x!=='number'||!Number.isFinite(x)))throw Error('finite-values-required');
    const nums=values.slice().sort((a,b)=>a-b),n=nums.length;if(!n)return null;
    const scale=Math.max(...nums.map(Math.abs))||1;let mean=0,m2=0;
    values.forEach((x,i)=>{const y=x/scale,d=y-mean;mean+=d/(i+1);m2+=d*(y-mean)});
    const quantile=q=>{
      const p=(n-1)*q,lo=Math.floor(p),hi=Math.ceil(p),f=p-lo,a=nums[lo],b=nums[hi];
      if(lo===hi||a===b)return a;
      const local=Math.max(Math.abs(a),Math.abs(b))||1;
      return ((1-f)*(a/local)+f*(b/local))*local;
    };
    const finite=x=>Number.isFinite(x)?x:null;
    return {count:n,min:nums[0],max:nums[n-1],mean:finite(mean*scale),median:finite(quantile(.5)),q1:finite(quantile(.25)),q3:finite(quantile(.75)),sample_stddev:n>1?finite(Math.sqrt(Math.max(0,m2/(n-1)))*scale):null};
  }
  function histogram(values,bins=8){
    if(!Array.isArray(values)||values.length>ANALYSIS_MAX_ROWS||values.some(n=>typeof n!=='number'||!Number.isFinite(n))||!Number.isInteger(bins)||bins<1||bins>50)throw Error('histogram-values');
    if(!values.length)return [];
    const lo=Math.min(...values),hi=Math.max(...values),scale=Math.max(Math.abs(lo),Math.abs(hi))||1,min=lo/scale,span=hi/scale-min;
    const buckets=Array.from({length:bins},(_,i)=>({label:String(i+1),count:0}));
    for(const value of values){const position=hi===lo?0:(value/scale-min)/span,index=Math.max(0,Math.min(bins-1,Math.floor(position*bins)));buckets[index].count++}
    return buckets;
  }
  function analyseTable(table,source){
    const {columns,rows}=table,stats=[],numeric=[];
    columns.forEach((name,i)=>{
      const values=rows.map(r=>r[i]),missing=values.filter(x=>!String(x).trim()).length;
      const parsed=values.map(strictNumeric).filter(x=>x!==null);
      const validNonMissing=rows.length-missing,asNumeric=parsed.length>0&&parsed.length/validNonMissing>=.8;
      const frequencies=new Map();
      for(const value of values){const key=String(value).trim()||null;frequencies.set(key,(frequencies.get(key)||0)+1);}
      const common=Array.from(frequencies,([value,count])=>({value:value===null?'(missing)':value,missing:value===null,count}))
        .sort((a,b)=>b.count-a.count||a.value.localeCompare(b.value)).slice(0,5);
      stats.push({name,missing,distinct:frequencies.size,type:asNumeric?'numeric':'categorical',
        numeric_count:parsed.length,invalid_numeric:asNumeric?validNonMissing-parsed.length:0,
        summary:asNumeric?numberStats(parsed):null,top_values:common.map(x=>({...x,value:x.value.slice(0,160)}))});
      if(asNumeric)numeric.push(i);
    });
    const correlations=[];
    for(let i=0;i<numeric.length;i++)for(let j=i+1;j<numeric.length;j++){
      const a=numeric[i],b=numeric[j],pairs=rows.map(r=>[strictNumeric(r[a]),strictNumeric(r[b])])
        .filter(([x,y])=>x!==null&&y!==null);
      if(pairs.length<3)continue;
      const sx=Math.max(...pairs.map(p=>Math.abs(p[0])))||1,sy=Math.max(...pairs.map(p=>Math.abs(p[1])))||1;
      const scaled=pairs.map(([x,y])=>[x/sx,y/sy]);
      const mx=scaled.reduce((sum,p)=>sum+p[0],0)/pairs.length,my=scaled.reduce((sum,p)=>sum+p[1],0)/pairs.length;
      let cov=0,vx=0,vy=0;
      for(const [x,y] of scaled){const dx=x-mx,dy=y-my;cov+=dx*dy;vx+=dx*dx;vy+=dy*dy;}
      const r=vx>0&&vy>0?cov/Math.sqrt(vx*vy):null;
      correlations.push({left:columns[a],right:columns[b],pairs:pairs.length,pearson_r:r===null||!Number.isFinite(r)?null:Math.max(-1,Math.min(1,r))});
    }
    return {schema:'nexus.local-analysis.v1',authority:'none',source:{name:source.name,sha256:source.sha,
      bytes:source.size,verification:'byte-identity-only'},limits:{max_rows:ANALYSIS_MAX_ROWS,max_columns:ANALYSIS_MAX_COLUMNS},
      rows:rows.length,columns:columns.length,column_stats:stats,correlations,notes:[
      'Exploratory descriptive analysis only; no causal inference, diagnosis, prediction or human judgment.',
      'Values are not independently verified; missing, invalid and mixed columns can affect statistics.',
      'Every delimited record counts as a row, including entirely empty records. A trailing record terminator does not add an extra row.',
      'Numeric parsing accepts dot/Arabic decimal marks and local digits; unsafe plain integers stay categorical and plain JSON integer digits are preserved. Nonzero inputs that underflow to zero are excluded. Binary64 summaries are approximate. Non-finite results are null; labels may be shortened. Pearson uses pairwise complete cases and is not causation.']};
  }
  function analysisGroups(table,index,metric,{limit=GROUP_PREVIEW_LIMIT}={}){
    if(!Array.isArray(table?.columns)||!table.columns.length||table.columns.length>ANALYSIS_MAX_COLUMNS||!Array.isArray(table.rows)||table.rows.length>ANALYSIS_MAX_ROWS)throw Error('group-table');
    if(!Number.isInteger(index)||index< -1||index>=table.columns.length||!Number.isInteger(metric)||metric< -1||metric>=table.columns.length||!Number.isInteger(limit)||limit<1||limit>ANALYSIS_MAX_ROWS)throw Error('group-selection');
    if(index<0)return [];
    const groups=new Map();
    for(const row of table.rows){
      if(!Array.isArray(row)||row.length!==table.columns.length)throw Error('group-row');
      const key=String(row[index]).trim()||null,label=key===null?'(missing)':key;
      if(!groups.has(key))groups.set(key,{label,missing:key===null,count:0,values:[]});
      const item=groups.get(key);item.count++;
      if(metric>=0){const v=strictNumeric(row[metric]);if(v!==null)item.values.push(v);}
    }
    return Array.from(groups.values()).map(g=>({label:g.label,missing:g.missing,count:g.count,
      metric_mean:metric<0?null:numberStats(g.values)?.mean??null,numeric_n:g.values.length}))
      .sort((a,b)=>b.count-a.count||a.label.localeCompare(b.label)).slice(0,limit);
  }
  function groupReport(table,index,metric){
    const groups=analysisGroups(table,index,metric,{limit:ANALYSIS_MAX_ROWS});
    return {group_by:index<0?null:table.columns[index],metric:metric<0?null:table.columns[metric],group_count:groups.length,groups_complete:true,groups};
  }
function parse(text,extension){
 if(typeof text!=='string'||new TextEncoder().encode(text).length>ANALYSIS_MAX_BYTES)throw Error('text-budget');
 text=text.replace(/^\uFEFF/,'');const kind=String(extension).toLowerCase();
 if(kind==='json')return parseJsonTable(text);
 if(!['csv','tsv'].includes(kind))throw Error('unsupported-table');
 const rows=parseDelimited(text,kind==='tsv'?'\t':',');
 return normalizedTable(rows[0]||[],rows.slice(1));
}
root.NexusTable=Object.freeze({parse,parseDelimited,normalizedTable,parseJsonTable,strictNumeric,numberStats,histogram,analyseTable,analysisGroups,groupReport,GROUP_PREVIEW_LIMIT,MAX_BYTES:ANALYSIS_MAX_BYTES,MAX_ROWS:ANALYSIS_MAX_ROWS,MAX_COLUMNS:ANALYSIS_MAX_COLUMNS});
})(globalThis);
