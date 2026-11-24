// Explicit user-authored review dates only. No clock, storage, network, inference or mutation.
// Syntax: [review YYYY-MM-DD] note. An overdue review is not proof that a note is false.
export function reviewMemoryDates(notes,asOf,{enabled=false,isolated=false}={}){
 if(typeof enabled!=='boolean'||typeof isolated!=='boolean')throw Error('invalid-options');
 if(isolated||!enabled)return {status:isolated?'isolated':'off',overdue:[],due:[],future:[],undated:[],invalid:[]};
 function validDate(s){
  if(typeof s!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(s))return false;
  const [y,m,d]=s.split('-').map(Number);
  if(y<1||m<1||m>12||d<1)return false;
  const leap=y%4===0&&(y%100!==0||y%400===0);
  return d<=[31,leap?29:28,31,30,31,30,31,31,30,31,30,31][m-1];
 }
 if(!validDate(asOf)||!Array.isArray(notes)||notes.length>30)throw Error('invalid-memory-input');
 const result={status:'review_only',basis:'explicit_review_dates_not_verified_obsolescence',overdue:[],due:[],future:[],undated:[],invalid:[]};
 const scheduled=[];
 for(let i=0;i<notes.length;i++){
  const note=notes[i];
  if(typeof note!=='string'||!note.trim()||note.length>500)throw Error('invalid-note');
  if(!/^\[review(?:\s|\]|$)/i.test(note)){result.undated.push(i);continue}
  const match=/^\[review (\d{4}-\d{2}-\d{2})\] ([^\r\n]+)$/.exec(note);
  if(!match||!validDate(match[1])||!match[2].trim()){result.invalid.push(i);continue}
  scheduled.push({i,date:match[1]});
 }
 scheduled.sort((a,b)=>a.date<b.date?-1:a.date>b.date?1:a.i-b.i);
 for(const {i,date} of scheduled)result[date<asOf?'overdue':date===asOf?'due':'future'].push(i);
 return result;
}
