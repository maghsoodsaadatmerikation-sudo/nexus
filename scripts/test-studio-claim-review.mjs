import assert from 'node:assert/strict';
import '../web/studio-claim-review.js';
const R=globalThis.NexusClaimReview;
const sample='A study in 2025 included 200 patients. The rate increased by 15 percent. Treatment caused improvement.';
const result=R.review(sample);
assert.equal(result.schema,'nexus.claim-review.v1');
assert.equal(result.blocked,false);
assert.deepEqual(result.claims.map(x=>x.review_reason),['quantity-or-date','quantity-or-date','causal-or-associational']);
assert(result.claims.every(x=>x.verification==='not-checked'));
assert.equal(result.verified,false);
assert.equal(R.review('آمار این پژوهش شامل ۲۵۰ نفر بوده است.').claims[0].review_reason,'quantity-or-date');
assert.equal(R.review('What is this? Please click here.').claims.length,0);
assert.equal(R.review('```js\nconst password = 42;\n```\nThe 2025 report included 20 patients.').claims.length,1);
assert.equal(R.review('The 2025 report included 20 patients. The 2025 report included 20 patients.').claims.length,1);
const many=Array.from({length:20},(_,i)=>`The 2025 trial ${i} enrolled 20 people.`).join('\n');
assert.equal(R.review(many).claims.length,12);
assert.equal(R.review(many).total_candidates,20);
assert.equal(R.review(many).truncated,true);
assert.match(R.checklist(sample),/not verified/);
assert.match(R.checklist(sample,'fa'),/تأییدنشده/);
assert.throws(()=>R.review('x'.repeat(24001)),/claim-review-input/);
assert.throws(()=>R.review({answer:'text'}),/claim-review-input/);
assert.throws(()=>R.checklist(sample,'unknown'),/claim-review-language/);
for(const secret of ['github_pat_'+'A'.repeat(40),'sk-proj-'+'b'.repeat(40),'AKIA'+'C'.repeat(16),'Authorization: Bearer '+'d'.repeat(40)]){
 const phrase='This claim was reported in 2025. '+secret;
 const blocked=R.review(phrase);
 assert.equal(blocked.blocked,true);
 assert.equal(blocked.claims.length,0);
 assert(!JSON.stringify(blocked).includes(secret));
 assert.throws(()=>R.checklist(phrase),/claim-review-possible-credentials/);
}
// A user-supplied reference is a review note, never a verified citation.
const manual=R.recordEvidence(sample,'c1',{
 source_url:'https://example.org/research?q=study',
 source_date:'2025-03-01',note:'Human entered a summary',assessment:'supports'
});
assert.equal(manual.claim_id,'c1');
assert.equal(manual.reviewer_assessment,'supports');
assert.equal(manual.verification,'not-independently-verified');
assert.equal(manual.source_retrieved,false);
assert.equal(manual.authority,'none');
assert.match(R.evidenceReport(sample,[manual]),/not independently verified/);
assert.match(R.evidenceReport(sample,[manual],'fa'),/تأیید مستقل نشده/);
assert.throws(()=>R.recordEvidence(sample,'c999',{}),/claim-evidence-id/);
assert.throws(()=>R.recordEvidence(sample,'c1',{source_url:'http://example.com'}),/claim-evidence-url/);
assert.throws(()=>R.recordEvidence(sample,'c1',{source_url:'https://user:password@example.org/'}),/claim-evidence-url/);
assert.throws(()=>R.recordEvidence(sample,'c1',{source_url:'https://example.org/',source_date:'2026-02-30'}),/claim-evidence-date/);
assert.throws(()=>R.recordEvidence(sample,'c1',{assessment:'supports',source_url:'https://example.org/'}),/claim-evidence-needs-source-and-date/);
assert.throws(()=>R.recordEvidence(sample,'c1',{assessment:'proven'}),/claim-evidence-input/);
assert.throws(()=>R.recordEvidence(sample,'c1',{unexpected:'tool-access'}),/claim-evidence-input/);
assert.throws(()=>R.recordEvidence(sample,'c1',{note:'github_pat_'+'Q'.repeat(40)}),/claim-evidence-private/);
assert.throws(()=>R.evidenceReport(sample,[manual,manual]),/claim-evidence-report/);
assert.throws(()=>R.recordEvidence('The report in 2025 used 15 people. github_pat_'+'Q'.repeat(40),'c1',{}),/claim-evidence-blocked/);
assert.throws(()=>R.evidenceReport(sample,[{claim_id:'c1',source_url:'https://example.org/',reviewer_assessment:'proven'}]),/claim-evidence-input/);
// Bounded substring detection is NOT evidence of source authenticity or claim truth.
const sourceText='Editorial note: This controlled synthetic text says exactly that 200 patients were enrolled in 2025.\nThe article also contains a second synthetic sentence.';
const literal='This controlled synthetic text says exactly that 200 patients were enrolled in 2025.';
const located=R.locateQuote(sample,'c1',{
 source_url:'https://example.org/synthetic-article',source_date:'2025-06-10',
 assessment:'unclear',note:'reviewed locally'
},sourceText,literal);
assert.equal(located.text_presence,'present-in-user-paste');
assert.equal(located.match_count,1);
assert.equal(located.claim_support,'not-assessed');
assert.equal(located.source_authenticity,'not-assessed');
assert.equal(located.source_origin,'human-pasted');
assert.equal(located.source_retrieved,false);
assert.equal(located.authority,'none');
assert.equal(located.verification,'not-independently-verified');
const unmatched=R.locateQuote(sample,'c1',{
 source_url:'https://example.org/synthetic-article',source_date:'2025-06-10'
},sourceText,'An entirely different synthetic quotation with no match.');
assert.equal(unmatched.text_presence,'not-found-in-user-paste');
assert.equal(unmatched.match_count,0);
const linebreak=R.locateQuote(sample,'c1',{
 source_url:'https://example.org/synthetic-article',source_date:'2025-06-10'
},'An article provided a 2025 result.\nIt described observations of 200 people.',
 'An article provided a 2025 result. It described observations of 200 people.');
assert.equal(linebreak.match_count,1);
assert.throws(()=>R.locateQuote(sample,'c1',{},sourceText,literal),/claim-quote-source-needed/);
assert.throws(()=>R.locateQuote(sample,'c1',{source_url:'https://example.org/',source_date:'2025-01-01'},sourceText,'tiny quote'),/claim-quote-input/);
assert.throws(()=>R.locateQuote(sample,'c1',{source_url:'https://example.org/',source_date:'2025-01-01'},'a'.repeat(12001),literal),/claim-quote-input/);
assert.throws(()=>R.locateQuote(sample,'c1',{source_url:'https://example.org/',source_date:'2025-01-01'},sourceText,'a'.repeat(401)),/claim-quote-input/);
assert.throws(()=>R.locateQuote(sample,'c1',{source_url:'https://example.org/',source_date:'2025-01-01'},sourceText+' github_pat_'+'X'.repeat(40),literal),/claim-quote-private/);
const safeRecord={...manual,source_text:sourceText,quotation:literal};
const manuscript=R.evidenceReport(sample,[safeRecord],'en');
assert(manuscript.includes(literal));
assert(manuscript.includes('present-in-user-paste'));
assert(!manuscript.includes('The article also contains a second synthetic sentence.'));
assert(!manuscript.includes('root.NexusClaimReview=Object.freeze'));
assert.match(manuscript,/Source authenticity and claim support have not been checked/);
assert.throws(()=>R.evidenceReport(sample,[{...safeRecord,quotation:'tiny'}]),/claim-quote-input/);
assert.throws(()=>R.evidenceReport(sample,[{...safeRecord,source_text:''}]),/claim-quote-input/);
assert.throws(()=>R.evidenceReport(sample,[{...safeRecord,verified:true}]),/claim-evidence-report/);
console.log('NEXUS local claim-review: PASS');
