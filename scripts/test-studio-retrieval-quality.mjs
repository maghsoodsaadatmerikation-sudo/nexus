// Deterministic, synthetic source-retrieval quality gate. This is NOT a live model benchmark.
import assert from 'node:assert/strict';
import '../web/studio-core.js';
const S = globalThis.NexusStudio;

const examples = [
 {name:'multi-term English', query:'orbital valve pressure', expected:'target', sources:[
  ['noise','The orbital diagram is ready for review.'],
  ['target','The orbital valve pressure was measured at 17 kPa.'],
  ['other','Separate pressure instruments are in storage.']]},
 {name:'technical fallback', query:'network fallback timeout', expected:'target', sources:[
  ['noise','network '.repeat(60)],
  ['target','The network fallback timeout is 3 seconds.'],
  ['other','A database timeout is configured separately.']]},
 {name:'Persian Arabic letter normalization', query:'کیفیت درمان', expected:'target', sources:[
  ['noise','درمان باید بر اساس ارزیابی باشد.'],
  ['target','كیفیت درمان در پرونده گزارش شده است.'],
  ['other','این آزمایش با خط مبنا متفاوت است.']]},
 {name:'Persian mixed joining', query:'یادگیری مدل', expected:'target', sources:[
  ['noise','مدل اولیه بررسی شد.'],
  ['target','يادگيری مدل در سه مرحله ثبت شد.'],
  ['other','پروتکل آزمون گزارش شد.']]},
 {name:'CJK matching', query:'月亮', expected:'target', sources:[
  ['noise','太阳升起了。'],
  ['target','夜晚的月亮很明亮。'],
  ['other','天气平静。']]},
 {name:'document-specific action', query:'archive restore confirmation', expected:'target', sources:[
  ['noise','The archive is ready.'],
  ['target','The archive restore confirmation receipt was generated.'],
  ['other','A restoration plan needs separate approval.']]},
 {name:'multiline provenance', query:'violet landmark', expected:'target', expectedLine:2, sources:[
  ['noise','The violet paint was stored.'],
  ['target','Unrelated first line.\nThe violet landmark is in the report.'],
  ['other','The landmark list was revised.']]},
];
let top1=0,found5=0,reciprocal=0;
for(const test of examples){
 const p=S.project('Synthetic fixture');
 p.sources=test.sources.map(([id,text])=>({id,name:id+'.txt',text}));
 const hits=S.retrieve(p,test.query);
 const index=hits.findIndex(h=>h.source_id===test.expected);
 if(index===0)top1++;
 if(index>=0)found5++;
 if(index>=0)reciprocal+=1/(index+1);
 assert(index>=0,test.name+' missing evidence from top 5');
 assert.equal(hits[0]?.source_id,test.expected,test.name+' lost best relevant passage');
 if(test.expectedLine)assert.equal(hits[index].line,test.expectedLine);
 assert(hits.every(h=>h.line>=1&&h.offset>=1&&p.sources.some(s=>s.id===h.source_id)));
 assert.deepEqual(S.retrieve(p,test.query).map(h=>h.source_id+':'+h.line+':'+h.offset),
  hits.map(h=>h.source_id+':'+h.line+':'+h.offset),'ranking must be reproducible');
}
const precisionAt1=top1/examples.length;
const recallAt5=found5/examples.length;
const mrrAt5=reciprocal/examples.length;
assert(precisionAt1>=6/7,'top-1 retrieval regressed against synthetic gold');
assert.equal(recallAt5,1,'synthetic evidence missing from shortlist');

const unanswerable=S.project('No matching evidence');
unanswerable.sources=[{id:'note',name:'note.txt',text:'The original dataset describes rust removal.'}];
assert.equal(S.retrieve(unanswerable,'quantum saffron').length,0,'invented lexical match');
const question=S.append(S.thread('No inference'),'user','quantum saffron','human');
const noSources=S.context(unanswerable,question,{sources:false});
const approved=S.context(unanswerable,question,{sources:true});
assert.equal(noSources.citations.length,0);
assert.equal(approved.citations.length,0,'no lexical support must not create a citation');
assert(!JSON.stringify(approved.messages).includes('rust removal'));

const attributed=S.project('Evidence with coordinates');
attributed.sources=[{id:'note',name:'note.txt',text:'No relevant line.\nOrbital valve pressure is 17.'}];
const t=S.append(S.thread('Question'),'user','orbital valve pressure','human');
const context=S.context(attributed,t,{sources:true});
assert.equal(context.citations.length,1);
assert.deepEqual(context.citations[0],{ref:'S1',source_id:'note',name:'note.txt',line:2,offset:1});
assert(context.messages[0].content.includes('lexical overlap does not prove a claim'));
assert(context.messages[0].content.includes('matched_terms'));
assert(context.messages[0].content.includes('[NXS:S1]'));
assert(context.messages[0].content.includes('"ref":"S1"'));
assert.equal(context.evidence_passages[0].ref,context.citations[0].ref);
assert(context.messages[0].content.includes('Orbital valve pressure is 17.'));
assert(!S.context(attributed,t,{sources:false}).messages.some(m=>m.content.includes('17.')));

const dispute=S.project('Disputed sources');
dispute.sources=[
 {id:'affirming',name:'affirming.txt',text:'The shipping status is approved.'},
 {id:'challenging',name:'challenging.txt',text:'The shipping status is disputed.'},
];
const disputeHits=S.retrieve(dispute,'shipping status');
assert.deepEqual(new Set(disputeHits.map(h=>h.source_id)),new Set(['affirming','challenging']),
 'distinct contradictory passages need to remain eligible for human review');

console.log(JSON.stringify({
 status:'PASS',test:'synthetic_studio_retrieval_quality',
 fixtures:examples.length,precision_at_1:precisionAt1,
 recall_at_5:recallAt5,mrr_at_5:mrrAt5,
 source_provenance:'PASS',source_opt_in:'PASS',unsupported_claim:'NO_CITATION',
 live_model_evaluated:false,
}));
