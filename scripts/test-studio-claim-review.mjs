import assert from 'node:assert/strict';
import {webcrypto} from 'node:crypto';
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
assert(manuscript.includes(literal.slice(0,-1)));
assert(manuscript.includes('present-in-user-paste'));
assert(!manuscript.includes('The article also contains a second synthetic sentence.'));
assert(!manuscript.includes('root.NexusClaimReview=Object.freeze'));
assert.match(manuscript,/Source authenticity and claim support have not been checked/);
assert.throws(()=>R.evidenceReport(sample,[{...safeRecord,quotation:'tiny'}]),/claim-quote-input/);
assert.throws(()=>R.evidenceReport(sample,[{...safeRecord,source_text:''}]),/claim-quote-input/);
assert.throws(()=>R.evidenceReport(sample,[{...safeRecord,verified:true}]),/claim-evidence-report/);
assert.throws(()=>R.evidenceReport(sample,[{...safeRecord,verification:'independently-verified'}]),/claim-evidence-report/);
assert.throws(()=>R.evidenceReport(sample,[{...safeRecord,statement:'Fake claimed assertion'}]),/claim-evidence-report/);
assert.throws(()=>R.evidenceReport(sample,[{...safeRecord,source_retrieved:true}]),/claim-evidence-report/);

// A manually reviewed navigation plan does not retrieve or validate a page.
const planned=R.planSourceOpen(sample,'c1','https://example.org/research/2025?source=human');
assert.equal(planned.schema,'nexus.source-open-plan.v1');
assert.equal(planned.url,'https://example.org/research/2025?source=human');
assert.equal(planned.hostname,'example.org');
assert.equal(planned.method,'explicit-browser-navigation');
assert.equal(planned.source_retrieved,false);
assert.equal(planned.source_verified,false);
assert.equal(planned.claim_verified,false);
assert.equal(planned.authority,'none');
for(const rejected of [
 'http://example.org/','https://localhost/p','https://admin@public.example.org/',
 'https://127.0.0.1/','https://2130706433/','https://[::1]/',
 'https://metadata.google.internal/','https://portal.local/',
 'https://example.org:8443/p','https://site.test/path',
 'https://foo.invalid/','https://host.onion/','https://foo.example/'
]){
 assert.throws(()=>R.planSourceOpen(sample,'c1',rejected),
  /claim-evidence-url|claim-source-public-host-required/,rejected);
}
assert.throws(()=>R.planSourceOpen(sample,'c1',''),/claim-source-url-required/);
assert.throws(()=>R.planSourceOpen(sample,'c13','https://example.org/'),/claim-evidence-id/);
assert.throws(()=>R.planSourceOpen('In 2025 the result was found. github_pat_'+'A'.repeat(40),
 'c1','https://example.org/'),/claim-evidence-blocked/);

// Crossref DOI metadata: consent, fixed host, size, origin, content type and truthful receipt.
const doi='10.5555/synthetic-2025',crossrefPlan=R.planCrossrefLookup(sample,'c1',doi);
assert.equal(crossrefPlan.url,'https://api.crossref.org/works/10.5555%2Fsynthetic-2025');
assert.equal(crossrefPlan.transmission,'DOI-only');
assert.equal(crossrefPlan.source_retrieved,false);
assert.equal(crossrefPlan.requires_consent,true);
for(const invalid of ['https://example.org','10.1/x','10.1234/','10.1234/%2Fbad','10.1234/x?token=secret',
 '10.1234/'+'x'.repeat(201),'10.1234/<script>']){
 assert.throws(()=>R.planCrossrefLookup(sample,'c1',invalid),/crossref-doi/);
}
assert.throws(()=>R.planCrossrefLookup(sample,'c13',doi),/claim-evidence-id/);
assert.throws(()=>R.planCrossrefLookup('The report in 2025 used 15 people. github_pat_'+'X'.repeat(40),'c1',doi),/claim-evidence-blocked/);
let crossrefCalls=0,seenOptions=null;
const crossrefFixture={message:{DOI:doi,title:['Synthetic <b>study</b>'],publisher:'Fictional Press',
 type:'journal-article',published:{'date-parts':[[2025,3,17]]}}};
const responseBody=JSON.stringify(crossrefFixture);
const createReply=(body=responseBody,opts={})=>({
 ok:opts.ok??true,status:opts.status??200,url:opts.url||crossrefPlan.url,
 headers:new Headers({'content-type':opts.type||'application/vnd.crossref-api-message+json',
  ...('length' in opts?{'content-length':String(opts.length)}:{})}),
 body:new Response(body).body
});
const mockCrossref=async(url,options)=>{
 crossrefCalls++;seenOptions=options;
 assert.equal(url,crossrefPlan.url);
 return createReply();
};
await assert.rejects(R.lookupCrossref(sample,'c1',doi,{fetcher:mockCrossref,cryptoProvider:webcrypto}),
 /crossref-consent-required/);
assert.equal(crossrefCalls,0);
const crossrefReceipt=await R.lookupCrossref(sample,'c1',doi,{
 consent:true,fetcher:mockCrossref,cryptoProvider:webcrypto
});
assert.equal(crossrefCalls,1);
assert.equal(seenOptions.credentials,'omit');
assert.equal(seenOptions.redirect,'error');
assert.equal(seenOptions.referrerPolicy,'no-referrer');
assert.equal(seenOptions.cache,'no-store');
assert.equal(seenOptions.mode,'cors');
assert.equal(seenOptions.method,'GET');
assert.equal(crossrefReceipt.response_url,crossrefPlan.url);
assert.equal(crossrefReceipt.title,'Synthetic <b>study</b>');
assert.equal(crossrefReceipt.deposited_publication_date,'2025-03-17');
assert.equal(crossrefReceipt.publisher,'Fictional Press');
assert.equal(crossrefReceipt.content_scope,'Crossref-bibliographic-metadata-only');
assert.equal(crossrefReceipt.source_retrieved,true);
assert.equal(crossrefReceipt.publisher_verified,false);
assert.equal(crossrefReceipt.claim_verified,false);
assert.equal(crossrefReceipt.authority,'none');
assert.match(crossrefReceipt.response_sha256,/^[a-f0-9]{64}$/);
assert.equal(crossrefReceipt.response_bytes,new TextEncoder().encode(responseBody).length);
for(const [label,reply,expected] of [
 ['unrelated-origin',createReply(responseBody,{url:'https://other.example/works/10.5555'}),/crossref-response-origin/],
 ['oversized-header',createReply(responseBody,{length:1000000}),/crossref-size/],
 ['oversized-stream',createReply('z'.repeat(66000)),/crossref-size/],
 ['wrong-type',createReply(responseBody,{type:'text/html'}),/crossref-type/],
 ['non-200',createReply(responseBody,{status:404,ok:false}),/crossref-response-unavailable/],
 ['invalid-json',createReply('not-json'),/crossref-json/],
 ['doi-mismatch',createReply(JSON.stringify({message:{DOI:'10.5555/not-the-requested'}})),/crossref-doi-mismatch/],
 ]){
 await assert.rejects(R.lookupCrossref(sample,'c1',doi,{
  consent:true,fetcher:async()=>reply,cryptoProvider:webcrypto
 }),expected,label);
}
const ctrl=new AbortController();ctrl.abort();
await assert.rejects(R.lookupCrossref(sample,'c1',doi,{
 consent:true,signal:ctrl.signal,cryptoProvider:webcrypto,fetcher:async()=>createReply()
}),/crossref-interrupted/);

// Europe PMC open-article XML: fixed endpoint, manual consent, strict safety checks.
// A quote match inside actual retrieved text is not verification of the answer.
const epmcQuote='The study included exactly two hundred participants in its sample.';
const epmcPlan=R.planEuropePmcFullText(sample,'c1','pmc123456',epmcQuote);
assert.equal(epmcPlan.pmcid,'PMC123456');
assert.equal(epmcPlan.url,'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC123456/fullTextXML');
assert.equal(epmcPlan.requires_consent,true);
assert.equal(epmcPlan.source_retrieved,false);
for(const badId of ['PM12345','PMC0','PMC001','PMC1/../../','https://www.ebi.ac.uk','PMC1234?x','PMC'+'1'.repeat(11)]){
 assert.throws(()=>R.planEuropePmcFullText(sample,'c1',badId,epmcQuote),/epmc-pmcid/);
}
assert.throws(()=>R.planEuropePmcFullText(sample,'c1','PMC123456','short'),/epmc-quote/);
assert.throws(()=>R.planEuropePmcFullText(sample,'c9','PMC123456',epmcQuote),/claim-evidence-input/);
const xml='<article><front><article-meta><article-id pub-id-type="pmc">123456</article-id>'+
 '<title-group><article-title>Fake <b>Story</b></article-title></title-group></article-meta></front>'+
 '<body><sec><p>Introduction. '+epmcQuote+'</p></sec></body></article>';
const parsedMock={documentElement:{localName:'article',getAttribute:()=> 'research-article'},getElementsByTagName:()=>[],
 querySelector(selector){
  if(selector==='article-id[pub-id-type="pmc"]')return {textContent:'123456'};
  if(selector==='body')return {
   textContent:'Introduction. '+epmcQuote,
   querySelectorAll:()=>[{textContent:'Introduction. '+epmcQuote,
     querySelector:()=>({textContent:'Results and interpretation'})}]
  };
  if(selector==='article-title')return {textContent:'Fake Story'};
  return null;
 }};
const xmlParser={parseFromString(text,mime){assert.equal(mime,'application/xml');return parsedMock}};
let epmcCalls=0,epmcOptions=null;
const pmcReply=(text=xml,options={})=>({
 ok:options.ok??true,status:options.status??200,url:options.url??epmcPlan.url,
 headers:new Headers({'content-type':options.type||'application/xml',
  ...('length' in options?{'content-length':String(options.length)}:{})}),
 body:new Response(text).body
});
const pmcMock=async(url,options)=>{
 epmcCalls++;epmcOptions=options;assert.equal(url,epmcPlan.url);
 return pmcReply();
};
await assert.rejects(R.lookupEuropePmcFullText(sample,'c1','PMC123456',epmcQuote,{
 fetcher:pmcMock,cryptoProvider:webcrypto,xmlParser
}),/epmc-consent-required/);
assert.equal(epmcCalls,0);
const pmcReceipt=await R.lookupEuropePmcFullText(sample,'c1','PMC123456',epmcQuote,{
 consent:true,fetcher:pmcMock,cryptoProvider:webcrypto,xmlParser
});
assert.equal(epmcCalls,1);
assert.equal(epmcOptions.credentials,'omit');
assert.equal(epmcOptions.redirect,'error');
assert.equal(epmcOptions.referrerPolicy,'no-referrer');
assert.equal(epmcOptions.cache,'no-store');
assert.equal(epmcOptions.mode,'cors');
assert.equal(epmcOptions.method,'GET');
assert.equal(pmcReceipt.article_title,'Fake Story');
assert.equal(pmcReceipt.article_type_as_deposited,'research-article');
assert.deepEqual(pmcReceipt.matching_section_headings,['Results and interpretation']);
assert.equal(pmcReceipt.section_context_is_support_verdict,false);
assert.equal(pmcReceipt.doctype_handling,'absent');
assert.equal(pmcReceipt.match_count,1);
assert.equal(pmcReceipt.quotation_presence,'present-in-retrieved-body');
assert.equal(pmcReceipt.source_retrieved,true);
assert.equal(pmcReceipt.source_authenticity,'not-independently-verified');
assert.equal(pmcReceipt.article_is_open_access,'endpoint-served-XML-not-license-certified');
assert.equal(pmcReceipt.claim_verified,false);
assert.equal(pmcReceipt.authority,'none');
assert.match(pmcReceipt.response_sha256,/^[0-9a-f]{64}$/);
assert(!JSON.stringify(pmcReceipt).includes('Introduction.'));
// Real JATS commonly advertises a public external DTD. Strip that declaration
// before parsing; do not load the network DTD and do not accept internal entities.
const jatsDoctype='<?xml version="1.0" encoding="utf-8"?>\n'+
 '<!DOCTYPE article PUBLIC "-//NLM//DTD JATS Journal Publishing DTD 1.2//EN" '+
 '"https://jats.nlm.nih.gov/publishing/1.2/JATS-journalpublishing1.dtd">\n';
const safeReader={parseFromString(data,mime){
 assert.equal(mime,'application/xml');
 assert(!data.includes('<!DOCTYPE'),'DTD must be stripped before DOMParser');
 assert(data.includes('<article>'));
 return parsedMock;
}};
const dtdAccepted=await R.lookupEuropePmcFullText(sample,'c1','PMC123456',epmcQuote,{
 consent:true,fetcher:async()=>pmcReply(jatsDoctype+xml),
 cryptoProvider:webcrypto,xmlParser:safeReader
});
assert.equal(dtdAccepted.doctype_handling,'simple-external-declaration-stripped');
assert.equal(dtdAccepted.match_count,1);
assert(dtdAccepted.response_bytes>pmcReceipt.response_bytes);
const missing=await R.lookupEuropePmcFullText(sample,'c1','PMC123456',
 'An unrelated sentence with no literal occurrence in the article.',{
 consent:true,fetcher:async()=>pmcReply(),cryptoProvider:webcrypto,xmlParser
});
assert.equal(missing.quotation_presence,'not-found-in-retrieved-body');
for(const [name,reply,expected] of [
 ['off-origin',pmcReply(xml,{url:'https://other.example/fullTextXML'}),/epmc-response-origin/],
 ['wrong-media',pmcReply(xml,{type:'text/html'}),/epmc-type/],
 ['declared-large',pmcReply(xml,{length:1048577}),/epmc-size/],
 ['actual-large',pmcReply('Z'.repeat(1048577)),/epmc-size/],
 ['status',pmcReply(xml,{ok:false,status:404}),/epmc-response-unavailable/],
 ['internal-DTD',pmcReply('<!DOCTYPE article [<!ENTITY x "EXPAND">]><article/>'),/epmc-xml-declaration/],
 ['duplicate-DTD',pmcReply(jatsDoctype+jatsDoctype+xml),/epmc-xml-declaration/],
 ['malformed-DTD',pmcReply('<!DOCTYPE article PUBLIC "x" "x" [not-safe]>'+xml),/epmc-xml-declaration/],
 ['Entity',pmcReply('<!ENTITY x "EXPAND"><article/>'),/epmc-xml-declaration/]
]){
 await assert.rejects(R.lookupEuropePmcFullText(sample,'c1','PMC123456',epmcQuote,{
  consent:true,fetcher:async()=>reply,cryptoProvider:webcrypto,xmlParser
 }),expected,name);
}
const wrongParser={parseFromString:()=>({
 documentElement:{localName:'article'},getElementsByTagName:()=>[],
 querySelector(key){return key==='article-id[pub-id-type="pmc"]'?{textContent:'999999'}:
   key==='body'?{textContent:epmcQuote}:null}
})};
await assert.rejects(R.lookupEuropePmcFullText(sample,'c1','PMC123456',epmcQuote,{
 consent:true,fetcher:async()=>pmcReply(),cryptoProvider:webcrypto,xmlParser:wrongParser
}),/epmc-article-mismatch/);
const cancelled=new AbortController();cancelled.abort();
await assert.rejects(R.lookupEuropePmcFullText(sample,'c1','PMC123456',epmcQuote,{
 consent:true,signal:cancelled.signal,fetcher:pmcMock,cryptoProvider:webcrypto,xmlParser
}),/epmc-interrupted/);
console.log('NEXUS local claim-review: PASS');
