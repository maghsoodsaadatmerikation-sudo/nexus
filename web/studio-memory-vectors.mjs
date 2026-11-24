// Pure cosine ranking of caller-supplied vectors only. No embedding generation.
// Host must establish matching project, note revision, vector provenance and consent.
// Scores are not probabilities, truth or calibrated semantic confidence.
export function rankMemoryVectors(entries,query,{enabled=false,isolated=false,limit=5,minimumSimilarity=0.25}={}){
 if(typeof enabled!=='boolean'||typeof isolated!=='boolean'||!Number.isInteger(limit)||limit<1||limit>10||!Number.isFinite(minimumSimilarity)||minimumSimilarity<0||minimumSimilarity>1)throw Error('invalid-options');
 if(isolated||!enabled)return {status:isolated?'isolated':'off',matches:[]};
 const modelId=x=>typeof x==='string'&&/^[a-zA-Z0-9][a-zA-Z0-9._:/-]{0,119}$/.test(x);
 if(!Array.isArray(entries)||entries.length>30||!query||!modelId(query.model_id)||!Array.isArray(query.vector)||query.vector.length<2||query.vector.length>1024)throw Error('invalid-vector-input');
 const dimension=query.vector.length;
 function unit(v){
  if(!Array.isArray(v)||v.length!==dimension)throw Error('vector-dimension-mismatch');
  let max=0;
  for(let i=0;i<dimension;i++){
   if(!Object.hasOwn(v,i)||typeof v[i]!=='number'||!Number.isFinite(v[i]))throw Error('invalid-vector-coordinate');
   max=Math.max(max,Math.abs(v[i]));
  }
  if(max===0)throw Error('zero-vector');
  const scaled=v.map(x=>x/max),norm=Math.sqrt(scaled.reduce((s,x)=>s+x*x,0));
  return scaled.map(x=>x/norm);
 }
 const q=unit(query.vector),seen=new Set(),matches=[];
 for(const entry of entries){
  if(!entry||!Number.isInteger(entry.index)||entry.index<0||entry.index>=30||seen.has(entry.index))throw Error('invalid-vector-index');
  if(entry.model_id!==query.model_id)throw Error('vector-model-mismatch');
  seen.add(entry.index);
  const v=unit(entry.vector);
  let cosine=Math.max(-1,Math.min(1,q.reduce((s,x,i)=>s+x*v[i],0)));
  if(cosine+1e-12<minimumSimilarity)continue;
  cosine=Math.round(cosine*1e6)/1e6;
  matches.push({index:entry.index,similarity:cosine});
 }
 matches.sort((a,b)=>b.similarity-a.similarity||a.index-b.index);
 return {status:'review_only',basis:'cosine_of_supplied_vectors_not_verified_relevance',matches:matches.slice(0,limit),truncated:matches.length>limit};
}
