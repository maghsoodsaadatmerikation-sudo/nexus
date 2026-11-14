// Isolate the production worksheet reader with decoded XML/ZIP adapters.
// Real ZIP, XML and browser acceptance is covered by the candidate browser witness.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import '../web/table-core.js';
const source=fs.readFileSync(new URL('../web/data-analysis-core.js',import.meta.url),'utf8');
const begin=source.indexOf('  async function parseXlsxTable(bytes){'),end=source.indexOf('  async function readAnalysisFile(item){',begin);
assert(begin>=0&&end>begin);
const MAIN='http://schemas.openxmlformats.org/spreadsheetml/2006/main',REL='http://schemas.openxmlformats.org/officeDocument/2006/relationships',PKG='http://schemas.openxmlformats.org/package/2006/relationships';
const node=(name,attrs={},children=[],textContent='',namespaceURI=MAIN)=>({name,localName:name,namespaceURI,children,textContent,getAttribute:key=>Object.hasOwn(attrs,key)?attrs[key]:null,getAttributeNS:(ns,key)=>ns===REL&&Object.hasOwn(attrs,'r:'+key)?attrs['r:'+key]:null});
const doc=root=>({documentElement:root,children:[root]});
const elements=(root,name)=>root.children.flatMap(child=>[...(child.name===name?[child]:[]),...elements(child,name)]);
const cell=(ref,value,type='inlineStr')=>node('c',{r:ref,t:type},[node(type==='inlineStr'?'t':'v',{},[],value)]);
const row=(number,cells)=>node('row',number===null?{}:{r:String(number)},cells);
const header=(ref='A1')=>row(1,[cell(ref,'Group'),cell('B1','Value')]);
const sheet=(name='Synthetic',rid='rId1',state='visible')=>node('sheet',{name,'r:id':rid,state});
const relation=(target='worksheets/sheet1.xml',id='rId1',extra={})=>node('Relationship',{Id:id,Type:REL+'/worksheet',Target:target,...extra},[],'',PKG);
const read=(rows,options={})=>{
 const files={'xl/workbook.xml':doc(node('workbook',{},[node('sheets',{},options.sheets||[sheet()])])),
  'xl/_rels/workbook.xml.rels':doc(node('Relationships',{},options.relations||[relation()],'',PKG)),
  'xl/worksheets/sheet1.xml':doc(node('worksheet',{},[node('sheetData',{},rows)])),...options.files};
 for(const path of options.remove||[])delete files[path];
 const zip={names:Object.keys(files),read:async path=>{if(!Object.hasOwn(files,path))throw Error('missing-entry');return files[path]}};
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
const selectedRows=[header(),row(2,[cell('A2','Actual'),cell('B2','9','n')])],decoy=[header(),row(2,[cell('A2','Decoy'),cell('B2','99','n')])];
const ordered=await read(decoy,{sheets:[sheet('Actual','rId9'),sheet('Decoy')],relations:[relation(),relation('worksheets/custom.xml','rId9')],files:{'xl/worksheets/custom.xml':doc(node('worksheet',{},[node('sheetData',{},selectedRows)]))}});
assert.equal(ordered.rows[0][1],'9');checks++;
assert.equal(ordered.worksheet.name,'Actual');checks++;
assert.equal(ordered.worksheet.sheet_count,2);checks++;
const standard=[header(),row(2,[cell('A2','A'),cell('B2','3','n')])];
for(const options of [
 {remove:['xl/workbook.xml']},{remove:['xl/_rels/workbook.xml.rels']},
 {sheets:[sheet('Unknown','missing')]},{relations:[relation(),relation()]},
 {relations:[relation('worksheets/sheet1.xml','rId1',{TargetMode:'External'})]},
 {relations:[relation('https://example.invalid/data.xml')]},
 {relations:[relation('//example.invalid/data.xml')]},
 {relations:[relation('../../outside.xml')]},
 {relations:[relation('worksheets/missing.xml')]},
 {relations:[relation('worksheets/sheet1.xml','rId1',{Type:REL+'/chartsheet'})]},
 {relations:[relation('worksheets/sheet1.xml','rId1',{Target:''})]},
 {sheets:[sheet(),sheet('Alias')]},
 {sheets:Array.from({length:21},(_,i)=>sheet('S'+i,'r'+i))},
 {files:{'xl/workbook.xml':doc(node('other'))}},
 {files:{'xl/worksheets/sheet1.xml':doc(node('not-a-worksheet'))}},
 {relations:[relation(),relation('strings.xml','strings',{Type:REL+'/sharedStrings'}),relation('strings.xml','strings2',{Type:REL+'/sharedStrings'})]}
]){await assert.rejects(read(standard,options),/xlsx-workbook/);checks++}
for(const target of ['/xl/worksheets/sheet1.xml','./worksheets/../worksheets/sheet1.xml']){assert.equal((await read(standard,{relations:[relation(target)]})).rows[0][1],'3');checks++}
const hidden=await read(standard,{sheets:[sheet('Hidden','rId1','hidden')]});assert.equal(hidden.worksheet.state,'hidden');checks++;
const sharedRows=[header(),row(2,[cell('A2','0','s'),cell('B2','1','s')])];
const shared=await read(sharedRows,{relations:[relation(),relation('strings/custom.xml','strings',{Type:REL+'/sharedStrings'})],files:{'xl/strings/custom.xml':doc(node('sst',{},[node('si',{},[node('t',{},[],'Actual')]),node('si',{},[node('t',{},[],'7')])]))}});
assert.deepEqual(JSON.parse(JSON.stringify(shared.rows)),[['Actual','7']]);checks++;
console.log(JSON.stringify({status:'PASS',checks,scope:'workbook-relationship-identity-and-cell-row-consistency',adapters:'decoded-xml-and-zip-stubs'}));
