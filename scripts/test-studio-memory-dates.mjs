import {reviewMemoryDates} from '../web/studio-memory-dates.mjs';
function runTests(reviewMemoryDates){
 let checks=0;
 const eq=(a,b)=>{checks++;if(JSON.stringify(a)!==JSON.stringify(b))throw Error('fixture mismatch '+checks)};
 const reject=fn=>{checks++;let rejected=false;try{fn()}catch{rejected=true}if(!rejected)throw Error('expected rejection '+checks)};
 const notes=Object.freeze(['[review 2026-11-20] private A','ordinary note','[review 2026-11-24] private B','[review 2026-12-01] private C','[review 2025-02-29] invalid','[review 2024-02-29] valid','[review 2026-11-20] another','[review 2026-11-24] ','[review 2026-11-25] متن فارسی']);
 const on={enabled:true},x=reviewMemoryDates(notes,'2026-11-24',on);
 eq(x.overdue,[5,0,6]);eq(x.due,[2]);eq(x.future,[8,3]);eq(x.undated,[1]);eq(x.invalid,[4,7]);eq(x.status,'review_only');
 eq(JSON.stringify(x).includes('private'),false);eq(JSON.stringify(x).includes('2026-11-24'),false);
 eq(reviewMemoryDates(null,null).status,'off');eq(reviewMemoryDates(null,null,{enabled:true,isolated:true}).status,'isolated');
 eq(reviewMemoryDates(['[review 2000-02-29] a','[review 1900-02-29] b'],'2000-02-29',on).invalid,[1]);
 eq(reviewMemoryDates(['[review 0000-01-01] a','[review 2026-04-31] b','[review 2026-13-01] c','[review 2026-01-00] d'],'2026-11-24',on).invalid,[0,1,2,3]);
 eq(reviewMemoryDates(['[review 2026-11-24] a\nb','[review] a','[REVIEW 2026-11-24] a'],'2026-11-24',on).invalid,[0,1,2]);
 eq(reviewMemoryDates(['somewhere [review 2026-11-24] a'],'2026-11-24',on).undated,[0]);
 eq(reviewMemoryDates([],'2026-11-24',on).overdue,[]);
 reject(()=>reviewMemoryDates(notes,'2026-2-01',on));reject(()=>reviewMemoryDates(notes,'2026-02-29',on));reject(()=>reviewMemoryDates(Array(31).fill('x'),'2026-11-24',on));reject(()=>reviewMemoryDates(['x'.repeat(501)],'2026-11-24',on));reject(()=>reviewMemoryDates(notes,'2026-11-24',{enabled:1}));
 eq(notes[0],'[review 2026-11-20] private A');eq(notes.length,9);
 return checks;
}
console.log('MEMORY REVIEW DATES: PASS ('+runTests(reviewMemoryDates)+' checks)');
