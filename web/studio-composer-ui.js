/* NEXUS Studio: honest chat composer and explicit archive shortcut.
 * Presentation only. All executions delegate to the existing reviewed actions.
 */
(()=>{'use strict';
const $=id=>document.getElementById(id);
const required=['conversation-card','message','guide','prepare','request-review','consent',
 'send-model','save','vault-card','language','branch-notice'];
if(required.some(id=>!$(id))||!window.NexusStudioUI?.uiStatus)return;
const words=(en,fa)=>document.documentElement.lang==='fa'?fa:en;
const box=document.createElement('section');box.id='studio-compose';box.className='studio-compose';
box.setAttribute('aria-label','Conversation actions');
const heading=document.createElement('strong');heading.id='studio-compose-heading';
const row=document.createElement('div');row.className='studio-compose-row';
const selectLabel=document.createElement('label');selectLabel.htmlFor='studio-compose-mode';
const select=document.createElement('select');select.id='studio-compose-mode';
for(const [value,en,fa] of [
 ['guide','Local reflection guide','راهنمای تأمل محلی'],
 ['model','Review AI model request','بازبینی درخواست مدل هوش مصنوعی']
]){const o=document.createElement('option');o.value=value;o.dataset.en=en;o.dataset.fa=fa;select.append(o)}
const send=document.createElement('button');send.type='button';send.id='studio-compose-send';
const save=document.createElement('button');save.type='button';save.id='studio-compose-save';save.className='secondary';
const privacy=document.createElement('p');privacy.id='studio-compose-privacy';privacy.className='help';
privacy.setAttribute('role','note');
const storage=document.createElement('p');storage.id='studio-compose-storage';storage.className='help';storage.setAttribute('role','status');storage.setAttribute('aria-live','polite');
selectLabel.append(select);row.append(selectLabel,send,save);
box.append(heading,row,privacy,storage);
$('branch-notice').after(box);
let running=false;
function refresh(){
 const state=window.NexusStudioUI.uiStatus();
 if(!state)return;
 const model=select.value==='model',ready=state.threadReady&&!state.archived&&!state.busy;
 heading.textContent=words('Reply using','پاسخ با');
 box.setAttribute('aria-label',words('Conversation actions','گزینه‌های گفتگو'));
 selectLabel.setAttribute('aria-label',words('Choose how to respond','روش پاسخ را انتخاب کن'));
 for(const opt of select.options)opt.textContent=words(opt.dataset.en,opt.dataset.fa);
 send.textContent=model?words('Review before sending','بازبینی پیش از ارسال'):words('Use local guide','استفاده از راهنمای محلی');
 send.disabled=!ready||!$('message').value.trim();
 send.setAttribute('aria-label',send.textContent);
 save.textContent=state.vaultUnlocked?words('Save encrypted session','ذخیرهٔ رمزگذاری‌شدهٔ نشست'):words('Set up private archive','تنظیم آرشیو خصوصی');
 // Never bypass the existing noForms() gate, including unread chat drafts.
 const pendingDraft=Boolean($('message').value.trim());
 save.disabled=state.busy||(state.vaultUnlocked&&(state.unsavedForms||pendingDraft));
 privacy.textContent=model?
  words('No message is sent by this button. Review the exact context and separately approve it. A configured model is required.',
        'این دکمه هیچ پیامی ارسال نمی‌کند؛ متن دقیق را بازبینی و جداگانه تأیید کن. اتصال مدل لازم است.'):
  words('Local guide only — not generative AI. It cannot read attached files.',
        'فقط راهنمای محلی، نه هوش مصنوعی مولد؛ فایل‌های پیوست را نمی‌خواند.');
 storage.textContent=state.vaultUnlocked?
  state.dirty||state.unsavedForms||pendingDraft?
   words('Work is not fully saved. Finish or clear draft fields, then save explicitly.',
         'همهٔ تغییرات ذخیره نشده‌اند. پیش‌نویس‌ها را تکمیل یا پاک کن و سپس صریحاً ذخیره کن.'):
   words('Encrypted archive unlocked. Use Save to retain changes; keep a separate encrypted backup.',
         'آرشیو رمزگذاری‌شده باز است. برای نگهداری تغییرات ذخیره کن و پشتیبان رمزگذاری‌شدهٔ جدا داشته باش.'):
  words('No encrypted archive is unlocked. This work can be lost if the tab closes.',
        'آرشیو رمزگذاری‌شده‌ای باز نیست. با بسته‌شدن برگه ممکن است کار از بین برود.');
}
function run(){
 if(running||send.disabled)return;
 running=true;
 try{
  if(select.value==='model'){
   $('prepare').click(); // Existing model-info, context, consent and safety checks.
   if(!$('request-review').hidden){
    const reviewHeading=$('request-review').querySelector('h3');
    if(reviewHeading){reviewHeading.tabIndex=-1;reviewHeading.focus({preventScroll:true})}
    $('request-review').scrollIntoView({block:'nearest'});
   }
  }else{
   $('guide').click(); // Existing source/attachment validation; never a network call.
  }
 }finally{running=false;refresh()}
}
send.addEventListener('click',run);
save.addEventListener('click',()=>{
 const state=window.NexusStudioUI.uiStatus();
 if(!state||state.busy||save.disabled)return;
 if(!state.vaultUnlocked){window.NexusStudioFocus?.openPanel('vault-card');$('passphrase').focus({preventScroll:true});return}
 $('save').click(); // Existing noForms() gate, vault encryption and user feedback.
 refresh();
});
select.addEventListener('change',refresh);
$('message').addEventListener('input',refresh);
$('message').addEventListener('keydown',event=>{
 if((event.ctrlKey||event.metaKey)&&event.key==='Enter'&&!event.isComposing){
  event.preventDefault();run(); // In model mode only opens the consent review.
 }
});
$('language').addEventListener('change',()=>queueMicrotask(refresh));
document.addEventListener('nexus-studio-state',refresh);
window.NexusStudioCompose={refresh,mode:()=>select.value};
refresh();
})();
