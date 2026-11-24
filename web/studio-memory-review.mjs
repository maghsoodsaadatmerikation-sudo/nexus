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

// Only explicitly structured notes: [fact] key = value.
// Unequal values are review candidates, not proven contradictions or stale facts.
export function reviewMemoryConflicts(notes,{enabled=false,isolated=false}={}){
 if(typeof enabled!=='boolean'||typeof isolated!=='boolean')throw Error('invalid-options');
 if(isolated||!enabled)return {status:isolated?'isolated':'off',groups:[]};
 if(!Array.isArray(notes)||notes.length>30)throw Error('invalid-memory-input');
 const groups=new Map();
 for(let index=0;index<notes.length;index++){
  const note=notes[index];
  if(typeof note!=='string'||!note.trim()||note.length>500)throw Error('invalid-note');
  const parts=/^\[fact\] ([\p{L}\p{N}][\p{L}\p{M}\p{N} _.-]{0,79}) = ([^\r\n]+)$/u.exec(note);
  if(!parts)continue;
  const key=parts[1].normalize('NFC').trim(),value=parts[2].normalize('NFC').trim();
  if(!value)continue;
  if(!groups.has(key))groups.set(key,new Map());
  const values=groups.get(key);
  if(!values.has(value))values.set(value,[]);
  values.get(value).push(index);
 }
 return {status:'review_only',basis:'different_explicit_values_not_verified_contradiction',
  groups:[...groups.values()].filter(values=>values.size>1).map(values=>({alternatives:[...values.values()]}))};
}

// Independent context ranking: normalized lexical phrases + explicit user aliases.
// This is not an embedding, truth check, automatic recall, or permission boundary.
export function rankMemoryContext(notes,query,{enabled=false,isolated=false,limit=5,aliases=[]}={}){
 if(typeof enabled!=='boolean'||typeof isolated!=='boolean'||!Number.isInteger(limit)||limit<1||limit>10)throw Error('invalid-options');
 if(isolated||!enabled)return {status:isolated?'isolated':'off',matches:[]};
 if(!Array.isArray(notes)||notes.length>30||typeof query!=='string'||query.length>24000)throw Error('invalid-memory-input');
 const tokens=s=>(s.normalize('NFKC').toLowerCase().replace(/[يى]/g,'ی').replace(/ك/g,'ک').replace(/[\u064b-\u065f\u0670]/g,'').match(/[\p{L}\p{M}\p{N}]+/gu)||[]).filter(w=>w.length>=2&&w.length<=80).slice(0,120);
 if(!Array.isArray(aliases)||aliases.length>20)throw Error('invalid-aliases');
 const mapped=new Map();
 for(let i=0;i<aliases.length;i++){
  const group=aliases[i];
  if(!Array.isArray(group)||group.length<2||group.length>6)throw Error('invalid-alias-group');
  for(const word of group){
   if(typeof word!=='string'||word.length>80||tokens(word).length!==1||tokens(word)[0]!==word.normalize('NFKC').toLowerCase().replace(/[يى]/g,'ی').replace(/ك/g,'ک').replace(/[\u064b-\u065f\u0670]/g,'').trim())throw Error('invalid-alias-token');
   const token=tokens(word)[0];
   if(mapped.has(token))throw Error('ambiguous-alias');
   mapped.set(token,i);
  }
 }
 const canonical=t=>mapped.has(t)?'alias:'+mapped.get(t):'term:'+t;
 const q=tokens(query),wanted=new Set(q.map(canonical)),seen=new Set(),rows=[];
 for(let index=0;index<notes.length;index++){
  const note=notes[index];
  if(typeof note!=='string'||!note.trim()||note.length>500)throw Error('invalid-note');
  const key=note.normalize('NFC').trim();
  if(seen.has(key))continue;
  seen.add(key);
  const raw=tokens(note),terms=new Set(raw.map(canonical));
  rows.push({index,raw,terms});
 }
 const frequencies=new Map();
 for(const {terms} of rows)for(const term of terms)frequencies.set(term,(frequencies.get(term)||0)+1);
 const pairs=a=>new Set(a.slice(1).map((x,i)=>a[i]+'\u0000'+x));
 const queryPairs=pairs(q),exactQuery=new Set(q),matches=[];
 for(const {index,raw,terms} of rows){
  const hits=[...terms].filter(t=>wanted.has(t));
  if(!hits.length)continue;
  // Integer inverse-document-frequency weights, unique hits, and literal phrase
  // bonus. Aliases contribute lexical matches but never literal phrase evidence.
  const score=hits.reduce((sum,t)=>sum+Math.floor(1000/(frequencies.get(t)||1)),0);
  const exact=[...new Set(raw)].filter(t=>exactQuery.has(t)).length;
  const phrases=[...pairs(raw)].filter(p=>queryPairs.has(p)).length;
  matches.push({index,score:score+exact*100+phrases*200,exact_terms:exact,phrase_pairs:phrases});
 }
 matches.sort((a,b)=>b.score-a.score||a.index-b.index);
 return {status:'review_only',basis:'bounded_lexical_context_and_explicit_aliases',matches:matches.slice(0,limit),truncated:matches.length>limit};
}
