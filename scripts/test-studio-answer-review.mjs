import '../web/studio-reply-format.js';
import assert from 'node:assert/strict';
const R=globalThis.NexusReplyFormat;
for(const lang of ['en','fa']){
 const prompt=R.answerReviewPrompt(lang);
 const path=[{role:'user',text:'Original question'},{role:'assistant',origin:'model',text:'Original answer'},{role:'user',text:prompt}];
 const msgs=path.map(n=>({role:n.role,content:n.text}));
 assert.equal(R.checkAnswerReviewContext(path,msgs),true);
 assert.equal(R.checkAnswerReviewContext(path,[{role:'user',content:'context'},...msgs]),true);
 assert.equal(R.checkAnswerReviewContext(path,msgs.slice(1)),false);
 assert.equal(R.checkAnswerReviewContext(path,[msgs[0],{...msgs[1],content:'changed'},msgs[2]]),false);
 assert.equal(R.checkAnswerReviewContext(path,[{...msgs[0],content:'changed'},...msgs.slice(1)]),false);
 assert.equal(R.checkAnswerReviewContext(path,[...msgs.slice(0,2),{...msgs[2],content:'changed'}]),false);
 assert.equal(R.checkAnswerReviewContext([path[0],{...path[1],origin:'local'},path[2]],msgs),false);
 assert.equal(R.checkAnswerReviewContext(path.slice(1),msgs),false);
 assert.equal(R.checkAnswerReviewContext(path,[msgs[1],msgs[0],msgs[2]]),false);
 assert.equal(R.checkAnswerReviewContext(path,null),false);
}
assert.notEqual(R.answerReviewPrompt('fa'),R.answerReviewPrompt('en'));
console.log('ANSWER REVIEW CONTEXT: PASS (21 checks)');
