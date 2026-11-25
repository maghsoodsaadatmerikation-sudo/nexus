// Local evidence review only. The caller must supply actual request passages
// and explicitly reviewed claim/quote relationships. Exact quotation, file
// identity and declared stance do not prove independence, entailment or truth.
export function reviewEvidenceClaims(passages,claims,{enabled=false,isolated=false}={}){
 const boundary={facts_verified:false,source_independence_verified:false,semantic_support_verified:false,automatic_resolution:false,execution_authorized:false,storage_authorized:false};
 if(typeof enabled!=='boolean'||typeof isolated!=='boolean')throw Error('invalid-review-options');
 if(!enabled||isolated)return {status:isolated?'isolated':'off',claims:[],...boundary};
 const ref=x=>typeof x==='string'&&/^[SA][1-9]\d?$/.test(x);
 const id=x=>typeof x==='string'&&/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$/.test(x);
 const positive=x=>Number.isSafeInteger(x)&&x>0;
 const exact=(x,keys)=>x&&typeof x==='object'&&!Array.isArray(x)&&Object.keys(x).sort().join('|')===keys;
 const norm=x=>x.normalize('NFC').replace(/\s+/gu,' ').trim();
 if(!Array.isArray(passages)||passages.length>10||!Array.isArray(claims)||claims.length<1||claims.length>20)throw Error('invalid-evidence-input');
 const index=new Map();
 for(const p of passages){
  if(!exact(p,'kind|line|offset|partial|ref|source_id|text')||!ref(p.ref)||index.has(p.ref)||!id(p.source_id)||!positive(p.line)||!positive(p.offset)||typeof p.partial!=='boolean'||typeof p.text!=='string'||!p.text.trim()||p.text.length>1800||!['project_source','one_turn_attachment'].includes(p.kind)||p.ref[0]!== (p.kind==='project_source'?'S':'A'))throw Error('invalid-evidence-passage');
  index.set(p.ref,p);
 }
 const seenClaims=new Set(),results=[];
 let total=0;
 for(const c of claims){
  if(!exact(c,'claim_id|judgments')||!id(c.claim_id)||seenClaims.has(c.claim_id)||!Array.isArray(c.judgments)||c.judgments.length>10||(total+=c.judgments.length)>80)throw Error('invalid-claim-review');
  seenClaims.add(c.claim_id);
  const rows=[],seen=new Set(),groups=new Map(),files=new Set();
  for(const j of c.judgments){
   if(!exact(j,'quote|ref|stance')||!ref(j.ref)||typeof j.quote!=='string'||j.quote.length<12||j.quote.length>500||norm(j.quote).length<12||!['supports','contradicts','uncertain'].includes(j.stance))throw Error('invalid-quote-judgment');
   const key=JSON.stringify([j.ref,j.quote,j.stance]);
   if(seen.has(key))throw Error('duplicate-quote-judgment');seen.add(key);
   const p=index.get(j.ref);
   if(!p){rows.push({ref:j.ref,stance:j.stance,status:'unknown_reference'});continue}
   if(!p.text.includes(j.quote)){rows.push({ref:j.ref,stance:j.stance,status:'quote_not_found'});continue}
   const q=norm(j.quote),content=norm(p.text);
   const g=groups.get(content)||{stances:new Set(),quotes:new Set(),refs:new Set(),files:new Set()};
   g.stances.add(j.stance);g.quotes.add(q);g.refs.add(j.ref);g.files.add(p.kind+':'+p.source_id);groups.set(content,g);
   files.add(p.kind+':'+p.source_id);
   rows.push({ref:j.ref,stance:j.stance,status:'exact_quote_found',partial:p.partial});
  }
  // Identical excerpts are grouped even when copied into different files.
  // Identical quotes across otherwise different excerpts are also flagged.
  const quoteGroups=new Map();
  for(const g of groups.values())for(const q of g.quotes)quoteGroups.set(q,(quoteGroups.get(q)||0)+1);
  const dispositions=[...groups.values()].map(g=>g.stances.has('supports')&&g.stances.has('contradicts')?'ambiguous_interpretation':g.stances.has('uncertain')?'uncertain':g.stances.has('supports')?'reported_support':'reported_contradiction');
  const support=dispositions.filter(x=>x==='reported_support').length,contradiction=dispositions.filter(x=>x==='reported_contradiction').length,ambiguous=dispositions.filter(x=>x==='ambiguous_interpretation').length,uncertain=dispositions.filter(x=>x==='uncertain').length;
  const invalid=rows.filter(x=>x.status!=='exact_quote_found').length;
  const duplicateExcerpts=[...groups.values()].some(g=>g.refs.size>1),duplicateQuotes=[...quoteGroups.values()].some(n=>n>1);
  const flags=[];
  if(invalid)flags.push('unmatched_evidence');
  if(rows.some(x=>x.partial))flags.push('partial_passage');
  if(duplicateExcerpts||duplicateQuotes)flags.push('repeated_content');
  if(ambiguous)flags.push('opposing_interpretations_of_same_excerpt');
  if(uncertain)flags.push('uncertain_interpretation');
  if(groups.size&&files.size===1)flags.push('single_file');
  const disposition=invalid?'reconcile_references':ambiguous?'reconcile_interpretations':support&&contradiction?'conflicting_reported_evidence':uncertain?'uncertain_evidence':support?'reported_support_only':contradiction?'reported_contradiction_only':'no_reviewed_evidence';
  results.push({claim_id:c.claim_id,disposition,exact_quote_count:rows.length-invalid,distinct_excerpt_count:groups.size,distinct_file_count:files.size,reported_support_excerpt_count:support,reported_contradiction_excerpt_count:contradiction,flags,judgments:rows});
 }
 return {status:'review_only',basis:'exact_substrings_and_declared_stances_not_verified_entailment_or_source_quality',claims:results,...boundary};
}
