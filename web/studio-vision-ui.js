/* NEXUS: reviewed, temporary image analysis inside chat. Image bytes never enter the archive. */
(() => {'use strict';
const $ = id => document.getElementById(id);
if (!window.NexusStudioUI?.selection || !$('studio-compose') || !$('conversation-card')) return;
const fa = () => document.documentElement.lang === 'fa';
const words = (en, persian) => fa() ? persian : en;
const panel = document.createElement('details'); panel.id = 'studio-vision-panel';
panel.className = 'studio-vision-panel';
const title = document.createElement('summary');
const help = document.createElement('p'); help.className = 'help';
const connectionActions=document.createElement('div');connectionActions.className='row';
const checkButton=document.createElement('button');checkButton.type='button';checkButton.className='secondary';checkButton.id='studio-vision-check';
const settingsButton=document.createElement('button');settingsButton.type='button';settingsButton.className='secondary';settingsButton.id='studio-vision-settings';
connectionActions.append(checkButton,settingsButton);
const label = document.createElement('label');
const picker = document.createElement('input'); picker.type = 'file'; picker.id = 'studio-vision-file';
picker.accept = '.png,.jpg,.jpeg,image/png,image/jpeg';
const preview = document.createElement('img'); preview.id = 'studio-vision-preview'; preview.alt = '';
preview.hidden = true; preview.style.cssText = 'max-width:min(100%,430px);max-height:320px;object-fit:contain;margin:12px 0;border-radius:12px';
const fileDetail = document.createElement('p'); fileDetail.className = 'help';
const questionLabel = document.createElement('label');
const question = document.createElement('textarea'); question.id = 'studio-vision-question'; question.maxLength = 4000;
question.rows = 2;
const reviewButton = document.createElement('button'); reviewButton.type = 'button'; reviewButton.id = 'studio-vision-review';
const reviewBox = document.createElement('div'); reviewBox.id = 'studio-vision-review-box'; reviewBox.hidden = true;
const reviewDetail = document.createElement('pre'); reviewDetail.id = 'studio-vision-request-detail';
reviewDetail.style.cssText = 'white-space:pre-wrap;overflow-wrap:anywhere';
const consentLabel = document.createElement('label'); consentLabel.className = 'inline';
const consent = document.createElement('input'); consent.type = 'checkbox'; consent.id = 'studio-vision-consent';
const consentText = document.createElement('span');
consentLabel.append(consent, consentText);
const sendButton = document.createElement('button'); sendButton.id = 'studio-vision-send';
sendButton.type = 'button'; sendButton.disabled = true;
reviewBox.append(reviewDetail, consentLabel, sendButton);
const clearButton = document.createElement('button'); clearButton.type = 'button'; clearButton.className = 'secondary';
clearButton.id = 'studio-vision-clear';
const status = document.createElement('p'); status.id = 'studio-vision-status'; status.setAttribute('role','status');
status.setAttribute('aria-live','polite'); status.className = 'help';
label.append(picker); questionLabel.append(question);
panel.append(title, help, connectionActions, label, preview, fileDetail, questionLabel, reviewButton, clearButton, reviewBox, status);
$('studio-compose').after(panel);
const quick = document.createElement('button'); quick.type = 'button'; quick.id = 'studio-vision-open';
quick.className = 'secondary';
$('nexus-zen-suggestions')?.append(quick);
quick.addEventListener('click', () => {panel.open = true;picker.focus()});
const MAX_IMAGE = 1500000, MAX_SIDE = 4096, MAX_PIXELS = 8000000;
let epoch = 0, image = null, pending = null, controller = null, sending = false, reading = false;
const msg = (en, persian) => {status.textContent = words(en,persian)};
const fingerprint = () => {
 const s = window.NexusStudioUI.selection();
 return s ? {projectId:s.projectId,threadId:s.threadId,head:s.head,revision:s.revision,branchBase:s.branchBase} : null;
};
const same = (a,b) => Boolean(a&&b&&a.projectId===b.projectId&&a.threadId===b.threadId&&
 a.head===b.head&&a.revision===b.revision&&a.branchBase===b.branchBase);
const chosenOrigin = () => {
 const u = new URL($('gateway').value.trim() || location.origin);
 if ((u.protocol!=='https:' && !(u.protocol==='http:' && ['127.0.0.1','[::1]'].includes(u.hostname))) ||
     u.username || u.password || u.search || u.hash || !['','/'].includes(u.pathname))
   throw Error('gateway-url');
 return u.origin;
};
function refresh(){
 const blocked = sending || reading || window.NexusStudioUI.uiStatus().busy;
 picker.disabled = blocked;
 question.disabled = blocked;
 checkButton.disabled = blocked;
 reviewButton.disabled = blocked || !image || !question.value.trim();
 clearButton.disabled = blocked;
 consent.disabled = blocked || !pending;
 sendButton.disabled = blocked || !pending || !consent.checked;
}
function cancel(){
 epoch++;
 controller?.abort(); controller = null;
 pending = null; consent.checked = false; reviewBox.hidden = true; sending = false;
 refresh();
}
function clear(){
 cancel();image = null;reading = false;question.value = '';picker.value = '';
 preview.removeAttribute('src');preview.hidden = true;fileDetail.textContent = '';status.textContent = '';
 refresh();document.dispatchEvent(new Event('nexus-studio-media-state'));
}
function relabel(){
 title.textContent = words('Analyze an image with AI (optional)','تحلیل تصویر با هوش مصنوعی (اختیاری)');
 help.textContent = words('Select one image and write a question. Your image stays on this device until you explicitly approve sending it to your configured model provider. An AI model is not bundled here.',
 'یک تصویر و سؤال انتخاب کن. تا پیش از تأیید صریح، تصویر روی دستگاه می‌ماند. مدل واقعی باید از قبل روی سرور پیکربندی شده باشد.');
 label.firstChild && (label.firstChild.nodeType===3) && label.firstChild.remove();
 label.insertBefore(document.createTextNode(words('Choose PNG or JPEG (up to 1.5 MB)','انتخاب PNG یا JPEG (تا ۱٫۵ مگابایت)')),picker);
 questionLabel.firstChild && (questionLabel.firstChild.nodeType===3) && questionLabel.firstChild.remove();
 questionLabel.insertBefore(document.createTextNode(words('Question about the image','پرسش دربارهٔ تصویر')),question);
 question.placeholder = words('What is visible in this image?','در این تصویر چه دیده می‌شود؟');
 checkButton.textContent = words('Check vision connection (no image sent)','بررسی اتصال بینایی (بدون ارسال تصویر)');
 settingsButton.textContent = words('Model connection settings','تنظیمات اتصال مدل');
 reviewButton.textContent = words('Review image and provider','بازبینی تصویر و ارائه‌دهنده');
 clearButton.textContent = words('Remove image and clear','حذف تصویر و پاک‌سازی');
 consentText.textContent = words('I have inspected this exact image and question. Send them once to the named model provider; its own retention and usage policies may apply.',
 'این تصویر و سؤال را بررسی کردم؛ با ارسال یک‌باره به ارائه‌دهندهٔ مشخص‌شده و سیاست نگه‌داری احتمالی آن موافقم.');
 sendButton.textContent = words('Send reviewed image','ارسال تصویر تأییدشده');
 quick.textContent = words('Image','تصویر');
}
const formatDigest = bytes => Array.from(new Uint8Array(bytes),n=>n.toString(16).padStart(2,'0')).join('');
function readAsDataURL(file){
 return new Promise((resolve,reject)=>{
  const reader = new FileReader();
  reader.onload = () => resolve(reader.result);
  reader.onerror = reader.onabort = () => reject(Error('read-failed'));
  reader.readAsDataURL(file);
 });
}
picker.addEventListener('change',async () => {
 const f = picker.files?.[0];cancel();image = null;fileDetail.textContent = '';
 preview.removeAttribute('src');preview.hidden = true;status.textContent = '';
 if (!f) {refresh();return}
 if (!['image/png','image/jpeg'].includes(f.type) || !f.size || f.size > MAX_IMAGE){
  picker.value = '';msg('Please select a PNG/JPEG no larger than 1.5 MB.','فقط PNG/JPEG کوچک‌تر از ۱٫۵ مگابایت پذیرفته می‌شود.');refresh();return;
 }
 const current = ++epoch; reading = true;refresh();
 try {
  const [bytes,url] = await Promise.all([f.arrayBuffer(),readAsDataURL(f)]);
  if (current!==epoch) return;
  const b64 = String(url).split(',')[1];
  if (!b64 || !String(url).startsWith('data:'+f.type+';base64,')) throw Error('invalid-image');
  preview.src = String(url);await preview.decode();
  if (current!==epoch) return;
  const width = preview.naturalWidth, height = preview.naturalHeight;
  if (!width || !height || width>MAX_SIDE || height>MAX_SIDE || width*height>MAX_PIXELS) throw Error('image-dimensions');
  const digest = formatDigest(await crypto.subtle.digest('SHA-256',bytes));
  if (current!==epoch) return;
  image = {mime:f.type,base64:b64,bytes:f.size,width,height,digest,filename:f.name};
  preview.hidden = false;
  fileDetail.textContent = f.name + ' · ' + width + '×' + height + ' · ' + f.size + ' bytes · SHA-256: ' + digest;
  msg('Image ready locally; no upload has happened.','تصویر روی دستگاه آماده است و هنوز ارسال نشده.');
 } catch {
  if(current===epoch){image=null;preview.removeAttribute('src');preview.hidden=true;picker.value='';
   msg('Image could not be decoded safely.','تصویر به شکل ایمن قابل بازخوانی نیست.')}
 } finally {if(current===epoch){reading=false;refresh();document.dispatchEvent(new Event('nexus-studio-media-state'))}}
});
clearButton.addEventListener('click',()=>{if(!clearButton.disabled){clear();msg('Image and question removed from this tab.','تصویر و پرسش از این تب پاک شدند.')}});
settingsButton.addEventListener('click',()=>{
 const settings=$('studio-model-settings');if(!settings)return;
 if(document.documentElement.classList.contains('studio-focus-mode')&&
    !document.documentElement.classList.contains('nexus-chat-options-open'))$('nexus-zen-more')?.click();
 settings.open=true;settings.scrollIntoView({block:'nearest'});$('gateway').focus({preventScroll:true});
});
question.addEventListener('input',()=>{cancel();refresh()});
consent.addEventListener('change',refresh);
checkButton.addEventListener('click',async()=>{
 if(checkButton.disabled)return;
 cancel();const current=++epoch;
 let origin;
 try{origin=chosenOrigin()}catch{
  msg('Open Model connection settings and enter a valid HTTPS gateway.','تنظیمات اتصال مدل را باز کن و درگاه HTTPS معتبر وارد کن.');return;
 }
 const abort=new AbortController();controller=abort;
 const timer=setTimeout(()=>abort.abort(),10000);
 try{
  const response=await fetch(origin+'/studio-api/vision-status',
   {credentials:'omit',cache:'no-store',redirect:'error',signal:abort.signal});
  if(!response.ok)throw Error('status-'+response.status);
  const body=await response.text();if(body.length>8000)throw Error('status-too-large');
  const info=JSON.parse(body);
  if(current!==epoch)return;
  if(info.authority!=='none'||typeof info.configured!=='boolean')throw Error('invalid-status');
  if(!info.configured){
   if(info.reason==='limit-reached')
    msg('The vision attempt limit for this server process has been reached. Operator action is required; no image was sent.',
     'سقف تلاش‌های تحلیل تصویر در این فرایند سرور تکمیل شده است. به اقدام اپراتور نیاز است؛ تصویری ارسال نشد.');
   else if(info.reason==='limit-unconfigured')
    msg('The operator has not configured a bounded vision request limit. No image was sent.',
     'سقف محدود درخواست‌های بینایی توسط اپراتور پیکربندی نشده است. تصویری ارسال نشد.');
   else
    msg('Gateway reached. Vision is not enabled or no model is configured; no image was sent.',
     'درگاه در دسترس است؛ مدل بینایی فعال یا پیکربندی نشده است. تصویری ارسال نشد.');
  }else if(typeof info.model==='string'&&info.model.trim()&&typeof info.provider_host==='string'&&info.provider_host.trim()){
   msg('Gateway reports '+info.model+' at '+info.provider_host+' configured. No image was sent; real vision quality is not verified.',
    'درگاه پیکربندی مدل '+info.model+' را گزارش می‌کند. تصویری ارسال نشد و کیفیت تحلیل هنوز تأیید نشده است.');
  }else throw Error('invalid-status');
 }catch{
  if(current===epoch)msg('Cannot check the gateway. Review its URL, availability and permitted browser origin. No image was sent.',
   'بررسی درگاه ممکن نیست. آدرس، دسترسی و مجوز اتصال مرورگر را بررسی کن. تصویری ارسال نشد.');
 }finally{clearTimeout(timer);if(current===epoch){controller=null;refresh()}}
});
reviewButton.addEventListener('click',async () => {
 if(!image || reading || sending || !question.value.trim() || window.NexusStudioUI.uiStatus().busy)return;
 cancel();
 if(window.NexusStudioUI.uiStatus().archived){
  msg('Open an active conversation first.','ابتدا یک گفتگوی فعال باز کن.');return;
 }
 if(!window.NexusStudioUI.uiStatus().threadReady && !window.NexusStudioUI.startConversation()){
  msg('Start a conversation first.','ابتدا گفتگو را آغاز کن.');return;
 }
 if($('message').value.trim()){
  msg('Keep the main message as a draft or clear it before saving the image answer.','پیام اصلی را به‌عنوان پیش‌نویس نگه دار یا پیش از ثبت پاسخ تصویر آن را پاک کن.');return;
 }
 const current = ++epoch;
 const state = fingerprint(), origin = (()=>{try{return chosenOrigin()}catch{return null}})();
 if(!origin){msg('Configure a secure model gateway first.','ابتدا درگاه مدل امن را تنظیم کن.');return}
 const abort = new AbortController();controller=abort;
 const timer = setTimeout(()=>abort.abort(),10000);
 try {
  const response = await fetch(origin+'/studio-api/vision-status',
    {credentials:'omit',cache:'no-store',redirect:'error',signal:abort.signal});
  if(!response.ok)throw Error('status-'+response.status);
  const content = await response.text();if(content.length>8000)throw Error('status-too-large');
  const info = JSON.parse(content);
  if(current!==epoch || !same(state,fingerprint()))return;
  if(!info.configured || !/^[a-f0-9]{64}$/.test(info.configuration_id) ||
     typeof info.model!=='string' || typeof info.provider_host!=='string')
    throw Error('vision-not-configured');
  pending = {origin,selection:state,image,question:question.value.trim(),configuration_id:info.configuration_id,model:info.model};
  reviewDetail.textContent =
   words('Provider: ','ارائه‌دهنده: ')+info.provider_host+'\n'+
   words('Model: ','مدل: ')+info.model+'\n'+
   words('Gateway: ','درگاه: ')+origin+'\n'+
   words('Question: ','سؤال: ')+pending.question+'\n'+
   words('Image: ','تصویر: ')+image.filename+' ('+image.mime+', '+image.bytes+' bytes, '+image.width+'×'+image.height+')\n'+
   'SHA-256: '+image.digest+'\n'+
   words('The complete image, not just this preview, will be sent. No image bytes are saved to chat history.',
    'کل دادهٔ تصویر ارسال می‌شود، نه فقط پیش‌نمایش. بایت‌های تصویر در تاریخچهٔ گفتگو ذخیره نمی‌شوند.');
  consent.checked=false;reviewBox.hidden=false;
  msg('Review the image above, provider and question, then give consent to send.','تصویر، ارائه‌دهنده و سؤال را بازبینی کن و سپس رضایت بده.');
 }catch{
  if(current===epoch)msg('Vision is unavailable. Check the configured provider; nothing was uploaded.',
   'تحلیل تصویر در دسترس نیست. تنظیمات ارائه‌دهنده را بررسی کن؛ تصویری ارسال نشد.');
 }finally{clearTimeout(timer);if(current===epoch){controller=null;refresh()}}
});
sendButton.addEventListener('click',async () => {
 if(!pending || !consent.checked || sending || window.NexusStudioUI.uiStatus().busy)return;
 const task = pending;
 if(!same(task.selection,fingerprint()) || task.image!==image || task.question!==question.value.trim() ||
    task.origin!==chosenOrigin()){
  cancel();msg('The reviewed context changed. Review again.','اطلاعات تغییر کرده؛ دوباره بازبینی کن.');return;
 }
 const current = ++epoch, abort = new AbortController();controller=abort;sending=true;
 consent.checked=false;refresh();
 const timer = setTimeout(()=>abort.abort(),50000);
 try{
  const response=await fetch(task.origin+'/studio-api/vision',{
   method:'POST',mode:'cors',credentials:'omit',cache:'no-store',redirect:'error',
   headers:{'content-type':'application/json','authorization':'Bearer '+$('gateway-token').value},
   body:JSON.stringify({consent:true,configuration_id:task.configuration_id,prompt:task.question,
    mime_type:task.image.mime,image_base64:task.image.base64,max_output_tokens:1024}),
   signal:abort.signal
  });
  if(!response.ok)throw Error('model-'+response.status);
  const content=await response.text();if(content.length>30000)throw Error('reply-capacity');
  const output=JSON.parse(content);
  if(current!==epoch || !same(task.selection,fingerprint()))return;
  if(output.origin!=='model' || output.modality!=='image-and-text' || output.authority!=='none' ||
     output.model!==task.model || typeof output.text!=='string' || !output.text.trim() || output.text.length>24000)
    throw Error('bad-vision-reply');
  const prompt=task.question, answer=output.text, selection=task.selection;
  // Revoke and erase raw image before updating text-only chat state.
  clear();
  if(window.NexusStudioUI.appendVisionResult({prompt,answer,selection})){
   msg('Image analysis added to this temporary chat. Save the conversation explicitly if wanted.',
       'تحلیل تصویر به گفتگوی موقت افزوده شد. در صورت نیاز گفتگو را جداگانه ذخیره کن.');
   if(output.truncated)msg('The model reached its output limit.','پاسخ به سقف طول رسیده است.');
  }else msg('The conversation changed, so the reply was not saved.','گفتگو تغییر کرده و پاسخ ذخیره نشد.');
 }catch{
  if(current===epoch)msg('Image request failed; the provider may have received it. Review again before retrying.',
    'درخواست ناموفق بود؛ ممکن است تصویر به ارائه‌دهنده رسیده باشد. پیش از تلاش مجدد بازبینی کن.');
 }finally{
  clearTimeout(timer);
  if(current===epoch){sending=false;controller=null;pending=null;consent.checked=false;reviewBox.hidden=true;refresh()}
 }
});
document.addEventListener('nexus-studio-state',()=>{
 const s=fingerprint();
 if(pending && !same(s,pending.selection))cancel();
 refresh();
});
document.addEventListener('nexus-studio-private-clear',clear);
for(const id of ['gateway','gateway-token','model-engine']){
 $(id)?.addEventListener('input',cancel);
 $(id)?.addEventListener('change',cancel);
}
$('language').addEventListener('change',()=>queueMicrotask(relabel));
relabel();refresh();
window.NexusStudioVision=Object.freeze({clear,cancel,open:()=>{panel.open=true;picker.focus()},hasTransientWork:()=>Boolean(image||reading||sending)});
})();
