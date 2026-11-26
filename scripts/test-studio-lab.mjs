import assert from 'node:assert/strict';
import '../web/studio-lab.js';
const L=globalThis.NexusLab;let checks=0;const ok=f=>{f();checks++};
for(const args of [['wikipedia','','en'],['wikipedia','topic','evil.example'],['unknown','topic','en'],['crossref','x'.repeat(251)]])ok(()=>assert.throws(()=>L.researchRequest(...args)));
const u=new URL(L.researchRequest('wikipedia','x & origin=private','fa'));ok(()=>assert.equal(u.hostname,'fa.wikipedia.org'));ok(()=>assert.equal(u.searchParams.get('gsrsearch'),'x & origin=private'));ok(()=>assert.equal(u.searchParams.get('origin'),'*'));
const wiki={query:{pages:{1:{pageid:1,title:'<img src=x>',extract:'unverified excerpt'}}}};const w=L.results('wikipedia',wiki,'topic');ok(()=>assert.equal(w.length,1));ok(()=>assert.equal(w[0].url,'https://en.wikipedia.org/?curid=1'));ok(()=>assert(L.sourceText(w[0]).includes('Unverified source text')));ok(()=>assert.equal(L.results('wikipedia',{batchcomplete:''},'topic').length,0));ok(()=>assert.throws(()=>L.results('wikipedia',{error:{code:'bad'}},'topic')));
const c=L.results('crossref',{message:{items:[{DOI:'10.1234/a?b#c',title:['Paper'],author:[{given:'A',family:'B'}],published:{'date-parts':[[2020]]},type:'journal-article'},{DOI:'javascript:bad',title:['bad']}] }},'topic');ok(()=>assert.equal(c.length,1));ok(()=>assert.equal(c[0].kind,'bibliographic-metadata-only'));ok(()=>assert(c[0].url.includes('%3F')&&c[0].url.includes('%23')));ok(()=>assert(!c[0].excerpt.includes('verified finding')));
const pmcRequest=new URL(L.researchRequest('europepmc','sleep & secret=literal'));
ok(()=>assert.equal(pmcRequest.origin,'https://www.ebi.ac.uk'));
ok(()=>assert.equal(pmcRequest.searchParams.get('query'),'sleep & secret=literal'));
ok(()=>assert.equal(pmcRequest.searchParams.has('secret'),false));
const pmc={resultList:{result:[
 {title:'Literature',doi:'10.1234/article',pmid:'42',authorString:'A. Reader',pubYear:'2024',abstractText:'<b>Methods</b> Synthetic abstract.'},
 null,{title:'Another paper',pmcid:'PMC1234'},{title:'Invalid result',pmid:'javascript:foo'}
]}};
const abstracts=L.results('europepmc',pmc,'sleep');
ok(()=>assert.deepEqual(abstracts.map(x=>[x.url,x.kind]),[
 ['https://doi.org/10.1234/article','abstract-excerpt'],['https://europepmc.org/article/PMC/PMC1234','bibliographic-metadata-only']
]));
ok(()=>assert(abstracts[0].excerpt.includes('Methods Synthetic abstract.')&&!abstracts[0].excerpt.includes('<b>')));
ok(()=>assert.throws(()=>L.results('europepmc',{},'sleep')));
const searchHosts=[];
const broader=await L.researchPlan('all','sleep','en',undefined,undefined,async(url,options)=>{
 const host=new URL(url).host;searchHosts.push(host);
 assert.equal(options.credentials,'omit');
 if(host==='www.ebi.ac.uk')return Response.json(pmc);
 if(host==='api.crossref.org')return Response.json({message:{items:[{DOI:'10.1234/ARTICLE',title:['Metadata first']}]}});
 return Response.json(wiki);
});
ok(()=>assert.deepEqual(searchHosts,['en.wikipedia.org','api.crossref.org','www.ebi.ac.uk']));
ok(()=>assert.equal(broader.cards.filter(x=>x.url.toLowerCase()==='https://doi.org/10.1234/article').length,1));
ok(()=>assert.equal(broader.cards.find(x=>x.url==='https://doi.org/10.1234/article').kind,'abstract-excerpt'));
let seen;const result=await L.fetchResearch('wikipedia','explicit query','en',undefined,async(url,options)=>{seen={url,options};return new Response(JSON.stringify(wiki))});ok(()=>assert.equal(result.length,1));ok(()=>assert.equal(seen.options.credentials,'omit'));ok(()=>assert.equal(seen.options.redirect,'error'));ok(()=>assert.equal(seen.options.referrerPolicy,'no-referrer'));ok(()=>assert(!('authorization' in (seen.options.headers||{}))));
await assert.rejects(()=>L.fetchResearch('wikipedia','q','en',undefined,async()=>new Response('x'.repeat(160001))));checks++;
const batchUrls=[];
const partial=await L.researchBatch('both','solar fields','en',undefined,async(url,options)=>{
 batchUrls.push(new URL(url));assert.equal(options.credentials,'omit');
 return url.includes('wikipedia.org')?Response.json(wiki):new Response('',{status:503});
});
ok(()=>assert.deepEqual(partial.failed,['crossref']));
ok(()=>assert.equal(partial.cards.length,1));
ok(()=>assert.deepEqual(batchUrls.map(url=>[url.hostname,url.searchParams.get('gsrsearch')||url.searchParams.get('query')]),[['en.wikipedia.org','solar fields'],['api.crossref.org','solar fields']]));
const planRequests=[],progress=[];
const plan=await L.researchPlan('both',' solar fields \r\n\n solar farms \n solar fields','en',undefined,
 (...step)=>progress.push(step),async(url,options)=>{
  const dest=new URL(url),query=dest.searchParams.get('gsrsearch')||dest.searchParams.get('query');
  planRequests.push([dest.hostname,query]);assert.equal(options.credentials,'omit');
  return dest.hostname==='en.wikipedia.org'?Response.json(wiki):new Response('',{status:503});
 });
ok(()=>assert.deepEqual(planRequests,[['en.wikipedia.org','solar fields'],['api.crossref.org','solar fields'],
 ['en.wikipedia.org','solar farms'],['api.crossref.org','solar farms']]));
ok(()=>assert.deepEqual(progress,[[1,2],[2,2]]));
ok(()=>assert.equal(plan.cards.length,1));
ok(()=>assert.deepEqual(plan.cards[0].queries,['solar fields','solar farms']));
ok(()=>assert.equal(plan.successful,2));
ok(()=>assert.deepEqual(plan.failed,['crossref']));
ok(()=>assert(L.researchBrief(plan.cards).includes('Query: solar farms')));
for(const invalid of ['', 'one\ntwo\nthree\nfour\nfive', 'x'.repeat(251)]){
 await assert.rejects(()=>L.researchPlan('both',invalid,'en',undefined,undefined,()=>assert.fail('invalid plan fetched')));
 checks++;
}
const abort=new AbortController();
let calls=0;
const stopped=await L.researchPlan('wikipedia','first\nsecond','en',abort.signal,()=>abort.abort(),
 async()=>{calls++;return Response.json(wiki)});
ok(()=>assert.equal(calls,1));
ok(()=>assert.equal(stopped.timedOut,true));
ok(()=>assert.deepEqual(stopped.cards[0].queries,['first']));
const brief=L.researchBrief([...w,...c]);
ok(()=>assert(brief.includes('[1] <img src=x>')&&brief.includes('https://doi.org/')&&brief.includes('bibliographic-metadata-only')));
ok(()=>assert.throws(()=>L.researchBrief(Array(6).fill(w[0]))));
const comparison=L.researchComparisonSource({...c[0],excerpt:'first line\nsecond line'});
ok(()=>assert(comparison.text.includes(c[0].url)&&comparison.text.includes('bibliographic-metadata-only')&&
 comparison.text.endsWith('first line second line')&&!comparison.text.includes('\n')));
const longComparison=L.researchComparisonSource({...w[0],excerpt:'😀'.repeat(2000)});
ok(()=>assert(longComparison.text.length<=1600&&longComparison.text.endsWith(' […]')&&
 !/[\uD800-\uDBFF] \[…\]$/u.test(longComparison.text)));
for(const v of [null,{type:'pie',labels:['a'],values:[1]},{type:'bar',labels:[],values:[]},{type:'line',labels:['a'],values:[NaN]},{type:'bar',labels:['a'],values:[Infinity]},{type:'bar',labels:['a'],values:[1e13]},{type:'line',labels:['a','b'],values:[1]}])ok(()=>assert.throws(()=>L.chart(v)));
ok(()=>assert.deepEqual(L.chart({type:'bar',labels:['<script>'],values:[-2]}).values,[-2]));ok(()=>assert.equal(L.chart({type:'line',labels:['a'],values:[0],title:'Safe'}).title,'Safe'));
console.log(JSON.stringify({status:'PASS',checks,live_provider_tested:false,browser_sandbox_tested:false}));
