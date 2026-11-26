import '../web/studio-reply-format.js';
import assert from 'node:assert/strict';
const review=globalThis.NexusReplyFormat.reviewDraft;
const long='This is a sufficiently long paragraph intended to test that a duplicated passage is recognized without treating short repetitions as defects.';
const cases=[
 ['hello',{},[]],['',{},['empty_answer']],[' \n\t',{},['empty_answer']],
 ['hello',{truncated:true},['length_limit']],['```js\nx',{},['unclosed_code_fence']],
 ['```js\nx\n```',{},[]],['~~~\nx\n```',{},['unclosed_code_fence']],
 ['````\nx\n```\n````',{},[]],
 [long+'\n\n'+long,{},['repeated_paragraph']],['short\n\nshort',{},[]],
 ['```text\n'+long+'\n\n'+long+'\n```',{},[]],
 ['a\u0000b',{},['control_characters']],['a'.repeat(100001),{},['review_limit']],
 ['پاسخ فارسی\n\tمعتبر',{},[]],['a\r\nb',{},[]],
 [long+'\n\n'+long,{truncated:true},['length_limit','repeated_paragraph']],
 [' \n',{truncated:true},['length_limit','empty_answer']],
 ['~~~\n~~~not a close',{},['unclosed_code_fence']]
];
for(const [text,opts,findings] of cases){
 const result=review(text,opts);
 assert.deepEqual(result,{findings,facts_verified:false,automatic_rewrite:false});
}
assert.throws(()=>review(null),/invalid-draft-review/);
assert.throws(()=>review('x',{truncated:1}),/invalid-draft-review/);
console.log('STRUCTURAL DRAFT REVIEW: PASS ('+(cases.length+2)+' checks)');
