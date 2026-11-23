/* NEXUS source-only preview: local review without persistence or network. */
(()=>{'use strict';
const byId=id=>document.getElementById(id),form=byId('review-form'),answer=byId('answer'),results=byId('results'),language=byId('language');
const clearResults=()=>{results.replaceChildren()};
const el=(tag,text,klass)=>{const node=document.createElement(tag);node.textContent=text;if(klass)node.className=klass;return node};
form.addEventListener('submit',event=>{
 event.preventDefault();clearResults();const fa=language.value==='fa';
 try{
  const report=NexusClaimReview.review(answer.value);
  if(report.blocked){results.append(el('p',fa?'احتمال وجود کلید محرمانه؛ فهرست ساخته نشد.':'Possible credential detected; no checklist created.','danger'));return}
  results.append(el('h2',fa?'ادعاهای نیازمند بررسی':'Claims to review'));
  results.append(el('p',fa?'این موارد تأیید نشده‌اند. برای هر ادعا، منبع مستقل و تاریخ را بررسی کنید.':'These statements have NOT been verified. Check independent evidence and dates.'));
  for(const claim of report.claims){const article=el('article','', 'claim');article.append(el('div',claim.id+' · '+claim.review_reason,'kind'),el('p',claim.statement),el('div',fa?'وضعیت: بررسی‌نشده':'Status: not checked','hint'));results.append(article)}
  if(!report.claims.length)results.append(el('p',fa?'موردی پیدا نشد؛ به معنی درستی پاسخ نیست.':'No candidates found; accuracy is still unknown.'));
  if(report.truncated)results.append(el('p',fa?'فقط ۱۲ مورد نخست نمایش داده شده‌اند.':'Only the first 12 are displayed.'));
 }catch{results.append(el('p',fa?'ورودی معتبر نیست.':'Invalid input.','danger'))}
});
byId('clear').addEventListener('click',()=>{answer.value='';clearResults();answer.focus()});
})();
