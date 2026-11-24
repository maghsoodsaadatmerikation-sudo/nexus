// Pure rank fusion, not embedding generation or an authorization boundary.
// Caller must bind source results to the same actual project, note snapshot and consent.
// Scope tags are consistency checks, not cryptographic provenance. No storage or I/O.
export function fuseMemoryRankings(scope,lexical,vector=null,{enabled=false,isolated=false,limit=5}={}){
 if(typeof enabled!=='boolean'||typeof isolated!=='boolean'||!Number.isInteger(limit)||limit<1||limit>10)throw Error('invalid-options');
 if(isolated||!enabled)return {status:isolated?'isolated':'off',matches:[]};
 if(!scope||typeof scope.project_id!=='string'||!/^[a-zA-Z0-9-]{1,80}$/.test(scope.project_id)||!Number.isSafeInteger(scope.revision)||scope.revision<0||!Number.isInteger(scope.note_count)||scope.note_count<0||scope.note_count>30)throw Error('invalid-scope');
 const ranks=new Map();
 function add(source,kind){
  if(!source||source.project_id!==scope.project_id||source.revision!==scope.revision||source.note_count!==scope.note_count)throw Error('ranking-scope-mismatch');
  if(source.status!=='review_only'||typeof source.truncated!=='boolean'||!Array.isArray(source.matches)||source.matches.length>10)throw Error('invalid-ranking');
  const seen=new Set();
  for(let i=0;i<source.matches.length;i++){
   const row=source.matches[i],index=row?.index;
   if(!Number.isInteger(index)||index<0||index>=scope.note_count||seen.has(index))throw Error('invalid-ranking-index');
   seen.add(index);
   if(!ranks.has(index))ranks.set(index,{index,lexical_rank:null,vector_rank:null});
   ranks.get(index)[kind+'_rank']=i+1;
  }
 }
 add(lexical,'lexical');
 if(vector!==null)add(vector,'vector');
 // Reciprocal rank fusion: integer weights avoid incompatible raw score scales.
 // k=10 is an explicit, uncalibrated design choice for bounded top-10 lists.
 const weight=rank=>rank===null?0:Math.floor(1000000/(10+rank));
 const rows=[...ranks.values()].map(row=>({...row,score:weight(row.lexical_rank)+weight(row.vector_rank)}));
 rows.sort((a,b)=>b.score-a.score||a.index-b.index);
 return {status:'review_only',basis:'reciprocal_rank_fusion_not_verified_relevance',
  mode:vector===null?'lexical_only':'hybrid',vector_status:vector===null?'not_supplied':'supplied',
  matches:rows.slice(0,limit),truncated:rows.length>limit||lexical.truncated||(vector?.truncated??false)};
}
