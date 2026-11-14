import assert from 'node:assert/strict';
import '../web/table-core.js';
const T=NexusTable;let checks=0;
const check=fn=>{fn();checks++},source={name:'synthetic',sha:'raw-byte-identity',size:1};
for(const [kind,sep] of [['csv',','],['tsv','\t']]){
 const text=`Group${sep}Value\r\nA${sep}1\r\n${sep}\r\n""${sep}""\r\nB${sep}3\r\n`;
 const table=T.parse(text,kind),report=T.analyseTable(table,source);
 check(()=>assert.deepEqual(table.rows,[['A','1'],['',''],['',''],['B','3']]));
 check(()=>assert.equal(report.rows,4));
 check(()=>assert.deepEqual(report.column_stats.map(c=>c.missing),[2,2]));
 check(()=>assert.equal(report.column_stats[1].summary.count,2));
 check(()=>assert.equal(report.column_stats[1].summary.mean,2));
 const groups=T.groupReport(table,0,1);
 check(()=>assert.equal(groups.groups.reduce((n,g)=>n+g.count,0),report.rows));
 check(()=>assert.deepEqual(groups.groups.find(g=>g.missing),{label:'(missing)',missing:true,count:2,metric_mean:null,numeric_n:0}));
 check(()=>assert.deepEqual(T.parse(`Value\n""\n`,kind).rows,[['']]));
 check(()=>assert.deepEqual(T.parse(`Value\n\n`,kind).rows,[['']]));
 check(()=>assert.deepEqual(T.parse(`Value\n1\n\n2\n`,kind).rows,[['1'],[''],['2']]));
 check(()=>assert.deepEqual(T.parse(`Value\n"line1\n\nline2"\n`,kind).rows,[['line1\n\nline2']]));
 for(const suffix of ['', '\n','\r\n','\r'])check(()=>assert.deepEqual(T.parse('Value\n1'+suffix,kind).rows,[['1']]));
 check(()=>assert.throws(()=>T.parse('Value\n',kind),/table-shape/));
 check(()=>assert.throws(()=>T.parse('Value\n'+sep+'\n',kind),/row-width/));
 check(()=>assert.equal(T.parse('Value\n'+'""\n'.repeat(T.MAX_ROWS),kind).rows.length,T.MAX_ROWS));
 check(()=>assert.throws(()=>T.parse('Value\n'+'""\n'.repeat(T.MAX_ROWS+1),kind),/rows/));
}
check(()=>assert.deepEqual(T.parse('[{"Group":"A","Value":1},{"Group":"","Value":""},{"Group":"B","Value":3}]','json').rows,T.parse('Group,Value\nA,1\n,\nB,3\n','csv').rows));
console.log(JSON.stringify({status:'PASS',checks,scope:'empty-delimited-records-and-missing-case-counts'}));
