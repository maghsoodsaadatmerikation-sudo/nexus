// Local, review-only memory matching. No storage, network, model, or mutation.
export function reviewMemory(notes, query, {enabled=false, isolated=false, limit=5}={}) {
 if(typeof enabled!=='boolean'||typeof isolated!=='boolean'||!Number.isInteger(limit)||limit<1||limit>10)throw Error('invalid-options');
 if(isolated||!enabled)return {status:isolated?'isolated':'off',matches:[],duplicates:[]};
 if(!Array.isArray(notes)||notes.length>30||typeof query!=='string'||query.length>24000)throw Error('invalid-memory-input');
 for(const note of notes)if(typeof note!=='string'||!note.trim()||note.length>500)throw Error('invalid-note');
 const key=s=>s.normalize('NFC').trim();
 const terms=s=>new Set((s.normalize('NFKC').toLowerCase().replace(/[يى]/g,'ی').replace(/ك/g,'ک').replace(/[\u064b-\u065f\u0670]/g,'').match(/[\p{L}\p{M}\p{N}]+/gu)||[]).filter(w=>w.length>=2&&w.length<=80).slice(0,120));
 const wanted=terms(query),seen=new Map(),duplicates=[],matches=[];
 for(let index=0;index<notes.length;index++){
  const k=key(notes[index]);
  if(seen.has(k)){duplicates.push({index,first_index:seen.get(k)});continue}
  seen.set(k,index);
  const score=[...terms(notes[index])].filter(term=>wanted.has(term)).length;
  if(score)matches.push({index,score});
 }
 matches.sort((a,b)=>b.score-a.score||a.index-b.index);
 return {status:'review_only',basis:'lexical_overlap_not_semantic_verification',matches:matches.slice(0,limit),duplicates,truncated:matches.length>limit};
}
