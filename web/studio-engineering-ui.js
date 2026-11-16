/* Local-only Engineering Agent import/review panel in the Studio conversation.
   No server-side execution, direct Docker access, or model tool privileges. */
(function(){'use strict';
const E=window.NexusEngineering,$=id=>document.getElementById(id);
Object.assign(EN,{
 engineering:'Engineering Agent',engineeringHelp:'Review a local engineering proposal, a prepared-plan summary or an execution receipt. This panel cannot run code or authorize commands. Private proposal files may include source code and secrets; keep them on your own device.',
 engineeringInput:'Proposal or local operator summary (JSON)',engineeringImport:'Import a local JSON/TXT file',engineeringInspect:'Inspect safely',engineeringDownload:'Download proposal for operator',engineeringChat:'Attach reviewed summary to next chat',engineeringConsent:'I inspected this exact content and choose this action. A separate operator approval is required for any command.',engineeringNoExecution:'Review only — no shell, Docker, GitHub write access or network execution is available from this panel.',engineeringReady:'Validated as untrusted local data. Not independently verified.',engineeringInvalid:'Invalid or oversized engineering handoff. No action was performed.',engineeringReset:'Clear engineering draft',engineeringPrivate:'Private proposal: download only after review. Do not attach full code or secrets to chat automatically.'
});
Object.assign(FA,{
 engineering:'عامل مهندسی',engineeringHelp:'پیشنهاد مهندسی، خلاصهٔ برنامه یا رسید اجرا را بررسی کن. این پنل نه کدی اجرا می‌کند و نه مجوز فرمان می‌دهد. فایل پیشنهاد ممکن است حاوی کد یا اطلاعات محرمانه باشد؛ آن را خصوصی نگه دار.',
 engineeringInput:'پیشنهاد یا گزارش محلی عامل (JSON)',engineeringImport:'بارگذاری فایل محلی JSON یا TXT',engineeringInspect:'بازبینی ایمن',engineeringDownload:'دریافت پیشنهاد برای اپراتور',engineeringChat:'افزودن خلاصهٔ بررسی‌شده به گفت‌وگوی بعدی',engineeringConsent:'این محتوای دقیق را بررسی کرده‌ام و این اقدام را انتخاب می‌کنم؛ اجرای فرمان نیازمند تأیید مجزای اپراتور است.',engineeringNoExecution:'فقط بازبینی — اجرای Shell یا Docker، نوشتن در GitHub و اجرای شبکه‌ای از این پنل ممکن نیست.',engineeringReady:'دادهٔ محلی نامعتبر از نظر اعتماد، اما ساختار آن بررسی شد؛ راستی‌آزمایی مستقل نیست.',engineeringInvalid:'فایل مهندسی نامعتبر یا بزرگ است؛ هیچ اقدامی انجام نشد.',engineeringReset:'پاک‌کردن پیش‌نویس',engineeringPrivate:'پیشنهاد خصوصی: فقط پس از بررسی دریافت کن. کد کامل یا اسرار به صورت خودکار به گفتگو افزوده نمی‌شوند.'
});
let revision=0,approved=null;
const active=()=>($('projects')?.value||'')+'|'+(typeof threadId==='string'?threadId:'')+'|'+($('branch')?.value||'');
function refresh(){
 const okay=approved&&approved.raw===$('engineering-text').value&&approved.scope===active()&&$('engineering-consent').checked;
 $('engineering-download').disabled=!okay||approved?.view.kind!=='proposal';
 $('engineering-chat').disabled=!okay||approved?.view.kind==='proposal';
}
function invalidate(){revision++;approved=null;$('engineering-consent').checked=false;$('engineering-report').textContent='';$('engineering-status').textContent='';refresh()}
function clear(){invalidate();$('engineering-text').value='';$('engineering-file').value=''}
function inspect(){
 invalidate();const raw=$('engineering-text').value;
 try{const view=E.inspect(raw);approved={raw,view,scope:active()};$('engineering-report').textContent=E.report(view);$('engineering-status').textContent=t('engineeringReady');if(view.kind==='proposal')$('engineering-status').textContent+=' '+t('engineeringPrivate')}
 catch{$('engineering-status').textContent=t('engineeringInvalid')}
 refresh();
}
$('engineering-text').addEventListener('input',invalidate);
$('engineering-consent').onchange=refresh;
$('engineering-inspect').onclick=inspect;
$('engineering-reset').onclick=clear;
$('engineering-file').onchange=async event=>{
 invalidate();const file=event.target.files?.[0];event.target.value='';
 const stamp=revision,scope=active();
 if(!file||file.size>E.MAX_BYTES||file.size<1){$('engineering-status').textContent=t('engineeringInvalid');return}
 try{
  const bytes=await file.arrayBuffer();
  if(stamp!==revision||scope!==active())return;
  if(bytes.byteLength>E.MAX_BYTES)throw Error('size');
  const raw=new TextDecoder('utf-8',{fatal:true}).decode(bytes);
  $('engineering-text').value=raw;inspect();
 }catch{if(stamp===revision&&scope===active()){$('engineering-status').textContent=t('engineeringInvalid');refresh()}}
};
$('engineering-download').onclick=()=>{
 refresh();if($('engineering-download').disabled)return;
 const doc=approved;const blob=new Blob([doc.raw],{type:'application/json;charset=utf-8'}),url=URL.createObjectURL(blob);
 try{const a=document.createElement('a');a.href=url;a.download='nexus-proposal-'+doc.view.workspace+'.json';a.rel='noopener';a.click()}finally{setTimeout(()=>URL.revokeObjectURL(url),1000)}
};
$('engineering-chat').onclick=()=>{
 refresh();if($('engineering-chat').disabled)return;
 const v=approved.view;
 const staged=window.NexusStudioUI?.stageChatContext('Engineering '+v.kind+' · unverified',E.report(v));
 if(staged){invalidate()}else $('engineering-status').textContent=t('engineeringInvalid');
};
$('history').addEventListener('click',clear);
for(const id of ['projects','branch'])$(id).addEventListener('change',clear);
for(const id of ['new-project','new-thread','delete-project','archive-thread','delete-thread','undo-removal','lock','unlock','restore','erase','restore-file']){
 const node=$(id);if(node){node.addEventListener('click',clear);node.addEventListener('change',clear)}
}
window.NexusEngineeringUI=Object.freeze({clear,inspect});
applyLanguage();refresh();
})();
