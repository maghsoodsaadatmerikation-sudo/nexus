import '../web/studio-core.js';
import '../web/studio-reply-format.js';
import assert from 'node:assert/strict';
const S=globalThis.NexusStudio,audit=globalThis.NexusReplyFormat.auditReferenceMarkers;
const cases=[
 ['No references',[],'no_supplied_refs',[],[]],
 ['No references',['S1'],'no_markers',[],[]],
 ['[NXS:S1]',['S1'],'matched_markers',['S1'],[]],
 ['[NXS:S1] [NXS:A1] [NXS:S1]',['S1','A1'],'matched_markers',['S1','A1'],[]],
 ['[NXS:S2] [NXS:S1] [NXS:S2]',['S1'],'unknown_markers',['S1'],['S2']],
 ['[NXS:A1]',['S1'],'unknown_markers',[],['A1']],
 ['[NXS:S1]',[],'unknown_markers',[],['S1']],
 ['[NXS:S10]',['S1'],'unknown_markers',[],['S10']],
 ['[NXS:S0] [nxs:s1] [NXS:S01]',['S1'],'malformed_markers',[],[],3],
 ['[NXS:S1] [NXS:S0]',['S1'],'malformed_markers',['S1'],[],1],
 ['[NXS:S2] [NXS:PRIVATE_FIXTURE]',['S1'],'unknown_markers',[],['S2'],1],
 ['[NXS:S100] [NXS:A01] [NXS : S1] [NXS:S1',['S1'],'malformed_markers',[],[],4],
 ['[NXS:PRIVATE_FIXTURE',[],'malformed_markers',[],[],1],
 ['[NXS:S1] [NXS:A99]',['S1','A99'],'matched_markers',['S1','A99'],[],0],
 ['[NXS:'.repeat(1000),[],'malformed_markers',[],[],1000],
 ['a'.repeat(100001),['S1'],'limit',[],[]],
 ['متن [NXS:A1]',['A1'],'matched_markers',['A1'],[]]
];
for(const [text,refs,status,matched,unknown,malformed_count=0] of cases)assert.deepEqual(audit(text,refs),{status,matched,unknown,malformed_count,facts_verified:false});
assert.equal(JSON.stringify(audit('[NXS:PRIVATE_FIXTURE]',[])).includes('PRIVATE_FIXTURE'),false);
for(const refs of [null,['S1','S1'],['S0'],['A01'],['https://example.org']])assert.throws(()=>audit('x',refs),/invalid-reference-audit/);
assert.throws(()=>audit(null,[]),/invalid-reference-audit/);
const project=S.project('Reference test'),thread=S.append(S.thread('Chat'),'user','orchard trees','human');
project.sources=[{id:'source-1',name:'trees.txt',text:'Orchard trees grow.'}];
const attachments=[{id:'file-1',name:'notes.txt',text:'Orchard notes.'}];
const off=S.context(project,thread);
assert.deepEqual(off.citations,[]);
assert.deepEqual(off.attachments_supplied,[]);
const ctx=S.context(project,thread,{sources:true,attachments});
assert.deepEqual(ctx.citations.map(x=>x.ref),['S1']);
assert.deepEqual(ctx.attachments_supplied.map(x=>x.ref),['A1']);
assert.equal(ctx.messages[0].content.includes('"ref":"S1","name":"trees.txt"'),true);
assert.equal(ctx.messages[0].content.includes('"ref":"A1","source_id":"file-1"'),true);
assert.deepEqual(audit('[NXS:S1] [NXS:A1]',[...ctx.citations,...ctx.attachments_supplied].map(x=>x.ref)).unknown,[]);
assert.equal(ctx.messages.at(-1).content,'orchard trees');
assert.deepEqual(off.evidence_passages,[]);
assert.deepEqual(ctx.evidence_passages.map(p=>p.ref),['S1','A1']);
assert.equal(ctx.evidence_passages[0].text,'Orchard trees grow.');
assert.equal(ctx.evidence_passages[1].text,'Orchard notes.');
assert.equal(ctx.evidence_passages[0].partial,true);
assert.equal(ctx.evidence_passages.every(p=>ctx.messages[0].content.includes(JSON.stringify(p.text))),true);
assert.deepEqual(S.context(project,{...thread,isolated:true},{sources:true,attachments}).evidence_passages,[]);
console.log('REFERENCE MARKER AUDIT: PASS (39 checks)');
