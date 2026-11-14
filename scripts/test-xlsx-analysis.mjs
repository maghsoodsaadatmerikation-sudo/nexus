// Isolate the production worksheet reader with decoded XML/ZIP adapters.
// Real ZIP, XML and browser acceptance is covered by the candidate browser witness.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import '../web/table-core.js';
const source=fs.readFileSync(new URL('../web/data-analysis-core.js',import.meta.url),'utf8');
const begin=source.indexOf('  async function parseXlsxTable(bytes){'),end=source.indexOf('  async function readAnalysisFile(item){',begin);
assert(begin>=0&&end>begin);
const node=(name,attrs={},children=[],textContent='')=>({name,children,textContent,getAttribute:key=>Object.hasOwn(attrs,key)?attrs[key]:null});
const elements=(root,name)=>root.children.flatMap(child=>[...(child.name===name?[child]:[]),...elements(child,name)]);
const cell=(ref,value,type='inlineStr')=>node('c',{r:ref,t:type},[node(type==='inlineStr'?'t':'v',{},[],value)]);
const row=(number,cells)=>node('row',number===null?{}:{r:String(number)},cells);
const header=(ref='A1')=>row(1,[cell(ref,'Group'),cell('B1','Value')]);
const read=rows=>{
 const doc=node('worksheet',{},rows),zip={names:['xl/worksheets/sheet1.xml'],read:async()=>doc};
 const parse=vm.runInNewContext('('+source.slice(begin,end).trim()+')',{
  zipReader:()=>zip,xmlDocument:x=>x,xmlElements:elements,xmlText:(root,name)=>elements(root,name).map(n=>n.textContent).join(''),
  normalizedTable:NexusTable.normalizedTable,ANALYSIS_MAX_COLUMNS:NexusTable.MAX_COLUMNS
 });
 return parse(new Uint8Array());
};
let checks=0;const reject=async rows=>{await assert.rejects(read(rows),/xlsx-cell-row/);checks++};
for(const ref of ['A1','A0','A3','A999','A9007199254740993'])await reject([header(),row(2,[cell(ref,'A'),cell('B2','3','n')])]);
for(const ref of ['B1','B0','B3','B999'])await reject([header(),row(2,[cell('A2','A'),cell(ref,'3','n')])]);
await reject([header('A2'),row(2,[cell('A2','A'),cell('B2','3','n')])]);
await reject([header(),row(null,[cell('A3','A'),cell('B3','3','n')])]);
const valid=await read([header(),row(2,[cell('A2','A'),cell('B2','3','n')])]);assert.deepEqual(JSON.parse(JSON.stringify(valid.rows)),[['A','3']]);checks++;
const sparse=await read([header(),row(3,[cell('A3','A'),cell('B3','3','n')])]);assert.deepEqual(JSON.parse(JSON.stringify(sparse.rows)),[['',''],['A','3']]);checks++;
const inferred=await read([header(),row(null,[cell('A2','A'),cell('B2','3','n')])]);assert.deepEqual(JSON.parse(JSON.stringify(inferred.rows)),[['A','3']]);checks++;
const empty=await read([header(),row(2,[]),row(3,[cell('A3','B'),cell('B3','4','n')])]);assert.deepEqual(JSON.parse(JSON.stringify(empty.rows)),[['',''],['B','4']]);checks++;
for(const ref of ['A','2A','A2x','a2','A-2']){await assert.rejects(read([header(),row(2,[cell(ref,'A')])]),/xlsx-cell/);checks++}
await assert.rejects(read([header(),row(2,[cell('A2','A'),cell('A2','B')])]),/xlsx-width/);checks++;
console.log(JSON.stringify({status:'PASS',checks,scope:'worksheet-cell-and-row-coordinate-consistency',adapters:'decoded-xml-and-zip-stubs'}));
