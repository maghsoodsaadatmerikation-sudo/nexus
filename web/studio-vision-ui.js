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


/* Optional image generation beside chat; no automatic send or durable storage.
 * A separate explicit review and approval is required for each provider call.
 * This is deliberately inactive until an operator provisions the API.
 */
(() => {'use strict';
const $ = id => document.getElementById(id);
if (!window.NexusStudioUI?.selection || !$('studio-compose') || !$('nexus-zen-suggestions')) return;
const words = (en, fa) => document.documentElement.lang === 'fa' ? fa : en;
const create = (tag, id, klass) => {
 const item = document.createElement(tag);
 if (id) item.id = id;
 if (klass) item.className = klass;
 return item;
};
const panel = create('details','studio-imagegen-panel','studio-vision-panel');
const title = create('summary'), intro = create('p',null,'help');
const quick = create('button','studio-imagegen-open','secondary');
quick.type = 'button';
const promptLabel = create('label'), prompt = create('textarea','studio-imagegen-prompt');
prompt.rows = 3;prompt.maxLength = 2000;prompt.dir = 'auto';
const draftButton = create('button','studio-imagegen-use-draft','secondary');
draftButton.type = 'button';
const sizeLabel = create('label'), size = create('select','studio-imagegen-size');
for (const [value, description] of [
 ['1024x1024','Square · 1024 × 1024'],
 ['1536x1024','Landscape · 1536 × 1024'],
 ['1024x1536','Portrait · 1024 × 1536']
]) {
 const option = create('option');option.value = value;option.textContent = description;size.append(option);
}
const toolbar = create('div',null,'row');
const check = create('button','studio-imagegen-check','secondary'), review = create('button','studio-imagegen-review');
check.type = review.type = 'button';toolbar.append(check,review);
const reviewBox = create('section','studio-imagegen-approval');reviewBox.hidden = true;
const exact = create('pre','studio-imagegen-exact');
const consentLabel = create('label',null,'inline');
const consent = create('input','studio-imagegen-consent');consent.type = 'checkbox';
const consentText = create('span');
consentLabel.append(consent,consentText);
const submit = create('button','studio-imagegen-submit');submit.type='button';
reviewBox.append(exact,consentLabel,submit);
const result = create('section','studio-imagegen-output');result.hidden = true;
const image = create('img','studio-imagegen-preview');
image.alt = '';image.style.cssText = 'display:block;max-width:100%;max-height:510px;object-fit:contain;margin:12px 0;border-radius:12px';
const download = create('button','studio-imagegen-download','secondary');
download.type = 'button';
const dismiss = create('button','studio-imagegen-clear','secondary');
dismiss.type = 'button';
result.append(image,download,dismiss);
const notice = create('p','studio-imagegen-status','help');notice.setAttribute('role','status');
notice.setAttribute('aria-live','polite');
promptLabel.append(prompt);sizeLabel.append(size);
panel.append(title,intro,promptLabel,draftButton,sizeLabel,toolbar,reviewBox,result,notice);
$('studio-vision-panel')?.after(panel);
if (!panel.parentNode) $('studio-compose').after(panel);
$('nexus-zen-suggestions').append(quick);
let generation=0, pending=null, controller=null, busy=false, output=null;
const say = (en,fa) => {notice.textContent=words(en,fa)};
const selection = () => {
 const s=window.NexusStudioUI.selection?.()||{};
 return JSON.stringify([s.projectId||null,s.threadId||null,s.head||null,s.revision||null,s.branchBase||null]);
};
let selected = selection();
function gatewayOrigin(){
 const raw = $('gateway')?.value.trim() || location.origin;
 const u = new URL(raw);
 if ((u.protocol!=='https:' && !(u.protocol==='http:' && ['127.0.0.1','[::1]'].includes(u.hostname))) ||
   u.username || u.password || u.search || u.hash || !['','/'].includes(u.pathname)) throw Error('unsafe-gateway');
 return u.origin;
}
function resetApproval(){
 generation++;controller?.abort();controller=null;
 pending=null;consent.checked=false;reviewBox.hidden=true;
}
function eraseOutput(){
 output=null;image.removeAttribute('src');result.hidden=true;download.disabled=true;
}
function resetAll(){
 resetApproval();eraseOutput();prompt.value='';size.value='1024x1024';say('','');
 refresh();
}
function refresh(){
 const status=window.NexusStudioUI.uiStatus?.()||{};
 const blocked=busy||status.busy||status.archived||status.attachmentLoading;
 check.disabled=blocked;review.disabled=blocked||!prompt.value.trim();
 prompt.disabled=blocked;size.disabled=blocked;draftButton.disabled=blocked;
 consent.disabled=blocked||!pending;
 submit.disabled=blocked||!pending||!consent.checked;
 download.disabled=!output;dismiss.disabled=busy||!output;
}
function relabel(){
 title.textContent=words('Generate an image (optional AI)','ساخت تصویر با هوش مصنوعی (اختیاری)');
 intro.textContent=words(
  'A configured provider is required. Review the exact prompt, size and provider, then approve one request. The provider may retain your prompt or image. Outputs stay only in this tab until you download them.',
  'به ارائه‌دهندهٔ پیکربندی‌شده نیاز است. متن، اندازه و ارائه‌دهنده را بازبینی کن و هر درخواست را جدا تأیید کن. ارائه‌دهنده ممکن است اطلاعات را نگه دارد. تصویر تا دانلود فقط در همین برگه است.');
 promptLabel.firstChild?.nodeType===3 && promptLabel.firstChild.remove();
 promptLabel.insertBefore(document.createTextNode(words('Image description','توصیف تصویر')),prompt);
 sizeLabel.firstChild?.nodeType===3 && sizeLabel.firstChild.remove();
 sizeLabel.insertBefore(document.createTextNode(words('Canvas size','اندازهٔ تصویر')),size);
 prompt.placeholder=words('An original abstract landscape…','یک منظرهٔ انتزاعی اصیل…');
 draftButton.textContent=words('Copy current chat draft into image prompt','کپی پیش‌نویس چت در توصیف تصویر');
 check.textContent=words('Check image model (no prompt sent)','بررسی مدل تصویر (بدون ارسال متن)');
 review.textContent=words('Review exact image request','بازبینی درخواست ساخت تصویر');
 consentText.textContent=words(
  'I reviewed this exact prompt, size and provider. Send it once; the provider’s retention, billing and content policies apply.',
  'متن، اندازه و ارائه‌دهنده را بازبینی کرده‌ام. با ارسال یک‌باره و سیاست‌های نگهداری، هزینه و محتوا موافقم.');
 submit.textContent=words('Generate approved image','ساخت تصویر تأییدشده');
 download.textContent=words('Download generated image','دانلود تصویر ساخته‌شده');
 dismiss.textContent=words('Remove image from this tab','حذف تصویر از این برگه');
 quick.textContent=words('Generate image','ساخت تصویر');
 refresh();
}
async function statusRequest(){
 const origin=gatewayOrigin();
 const abort=new AbortController();controller=abort;
 const timer=setTimeout(()=>abort.abort(),10000);
 try{
  const r=await fetch(origin+'/studio-api/image-generation-status',{
   credentials:'omit',cache:'no-store',redirect:'error',signal:abort.signal
  });
  if(!r.ok)throw Error('image-gateway-unavailable');
  const text=await r.text();
  if(text.length>4000)throw Error('unbounded-status');
  const data=JSON.parse(text);
  if(data.authority!=='none'||typeof data.configured!=='boolean')throw Error('invalid-status');
  return {origin,data};
 }finally{clearTimeout(timer);if(controller===abort)controller=null}
}
quick.onclick=()=>{panel.open=true;prompt.focus({preventScroll:true})};
draftButton.onclick=()=>{
 const draft=$('message')?.value || '';
 if(!draft.trim()){say('The chat draft is empty.','پیش‌نویس چت خالی است.');return}
 if(draft.length>2000){say('Draft is longer than 2,000 characters; shorten it first.','پیش‌نویس بیشتر از ۲۰۰۰ نویسه است؛ ابتدا کوتاهش کن.');return}
 resetApproval();prompt.value=draft;refresh();
};
function changed(){
 resetApproval();refresh();
}
prompt.addEventListener('input',changed);
size.addEventListener('change',changed);
consent.addEventListener('change',refresh);
for(const id of ['gateway','gateway-token']) {
 $(id)?.addEventListener('input',changed);
 $(id)?.addEventListener('change',changed);
}
check.onclick=async()=>{
 if(check.disabled)return;
 resetApproval();const seq=++generation;
 try{
  const {data}=await statusRequest();
  if(seq!==generation)return;
  if(data.configured)
   say('Provider '+data.model+' reports configured; actual image quality has not been verified.',
       'مدل '+data.model+' پیکربندی شده گزارش می‌شود؛ کیفیت واقعی هنوز تأیید نشده است.');
  else say('Image generation is not enabled, or its usage limit has been reached. No prompt was sent.',
      'ساخت تصویر فعال نیست یا سقف درخواست تکمیل شده است. متنی ارسال نشد.');
 }catch{
  if(seq===generation)say('Cannot verify image generation gateway. No prompt was sent.',
                            'تأیید درگاه تصویر ممکن نیست. متنی ارسال نشد.');
 }finally{refresh()}
};
review.onclick=async()=>{
 if(review.disabled)return;
 resetApproval();const seq=++generation,scope=selection();
 let origin;
 try{
  const checked=await statusRequest();
  if(seq!==generation||scope!==selection())return;
  const d=checked.data;origin=checked.origin;
  if(!d.configured||!/^[a-f0-9]{64}$/.test(d.configuration_id)||
     !d.model||typeof d.model!=='string'||!d.provider_host||
     typeof d.provider_host!=='string')throw Error('provider-not-ready');
  pending={scope,origin,model:d.model,host:d.provider_host,configuration_id:d.configuration_id,
           prompt:prompt.value.trim(),size:size.value,token:$('gateway-token')?.value||''};
  exact.textContent=words('Provider: ','ارائه‌دهنده: ')+pending.host+'\n'+
    words('Model: ','مدل: ')+pending.model+'\n'+
    words('Gateway: ','درگاه: ')+origin+'\n'+
    words('Size: ','اندازه: ')+size.value+'\n'+
    words('Exact prompt:','متن دقیق:')+'\n'+pending.prompt+'\n'+
    words('No image is generated or saved before approval.','بدون تأیید، تصویری ساخته یا ذخیره نمی‌شود.');
  consent.checked=false;reviewBox.hidden=false;
  say('Review the exact details and approve once.','جزئیات را بازبینی و فقط همین درخواست را تأیید کن.');
 }catch{
  if(seq===generation)say('Image provider is unavailable; review the gateway settings. Nothing was sent.',
                          'درگاه ساخت تصویر آماده نیست؛ تنظیمات را بررسی کن. چیزی ارسال نشد.');
 }finally{refresh()}
};
submit.onclick=async()=>{
 if(submit.disabled||!pending||busy)return;
 const task=pending;
 let currentOrigin;
 try{currentOrigin=gatewayOrigin()}catch{currentOrigin=null}
 if(task.scope!==selection()||task.origin!==currentOrigin||
    task.prompt!==prompt.value.trim()||task.size!==size.value||
    task.token!==($('gateway-token')?.value||'')){
  resetApproval();say('Inputs changed. Review the request again.','ورودی‌ها تغییر کردند؛ دوباره بازبینی کن.');refresh();return;
 }
 const seq=++generation, abort=new AbortController();
 controller=abort;busy=true;consent.checked=false;pending=null;reviewBox.hidden=true;
 eraseOutput();refresh();
 const timer=setTimeout(()=>abort.abort(),65000);
 try{
  const r=await fetch(task.origin+'/studio-api/generate-image',{
   method:'POST',mode:'cors',cache:'no-store',credentials:'omit',redirect:'error',
   headers:{'content-type':'application/json','authorization':'Bearer '+task.token},
   body:JSON.stringify({consent:true,configuration_id:task.configuration_id,
                       prompt:task.prompt,size:task.size}),signal:abort.signal
  });
  if(!r.ok)throw Error('provider-'+r.status);
  const content=await r.text();
  if(content.length>8200000)throw Error('response-too-large');
  const data=JSON.parse(content);
  if(seq!==generation||task.scope!==selection())return;
  if(data.authority!=='none'||data.model!==task.model||
     !['image/png','image/jpeg'].includes(data.mime_type)||
     typeof data.image_base64!=='string'||
     data.image_base64.length>8000000||!data.image_base64.length||
     !/^[A-Za-z0-9+/]+={0,2}$/.test(data.image_base64))throw Error('invalid-image-response');
  // The gateway validates image bytes; data: avoids blob URL lifecycle leaks.
  const url='data:'+data.mime_type+';base64,'+data.image_base64;
  output={url,ext:data.mime_type==='image/png'?'png':'jpg'};
  image.src=url;result.hidden=false;download.disabled=false;
  say('Image received in this tab only. Choose Download to keep a copy.',
      'تصویر فقط در این برگه دریافت شد. برای نگه‌داری، دانلود را انتخاب کن.');
 }catch{
  if(seq===generation)say('Image generation failed; the provider may have received the prompt. Review before retrying.',
    'ساخت تصویر ناموفق بود؛ ممکن است ارائه‌دهنده متن را دریافت کرده باشد. پیش از تلاش دوباره بازبینی کن.');
 }finally{clearTimeout(timer);if(controller===abort)controller=null;busy=false;refresh()}
};
download.onclick=()=>{
 if(!output)return;
 const anchor=document.createElement('a');
 anchor.href=output.url;anchor.download='NEXUS-image.'+output.ext;
 document.body.append(anchor);anchor.click();anchor.remove();
};
dismiss.onclick=()=>{if(output){eraseOutput();say('Image removed from this tab.','تصویر از این برگه حذف شد.');refresh()}};
document.addEventListener('nexus-studio-state',()=>{
 const current=selection();
 if(current!==selected){selected=current;resetApproval();eraseOutput()}
 refresh();
});
document.addEventListener('nexus-studio-private-clear',resetAll);
$('language')?.addEventListener('change',()=>queueMicrotask(relabel));
relabel();refresh();
})();


/* NEXUS local image studio: original pixels remain on-device, full frame only.
 * Brightness, contrast and saturation are reversible; export is explicit.
 * This is not a generative model and does not upload images.
 */
(() => {'use strict';
const $=id=>document.getElementById(id);
if(!$('studio-compose')||!$('nexus-zen-suggestions'))return;
const words=(en,fa)=>document.documentElement.lang==='fa'?fa:en;
const el=(tag,id)=>{const node=document.createElement(tag);if(id)node.id=id;return node};
const panel=el('details','studio-local-image-panel');panel.className='studio-vision-panel';
const summary=el('summary'),help=el('p');help.className='help';
const actions=el('div');actions.className='row';
const fileLabel=el('label'),file=el('input','studio-local-image-file');
file.type='file';file.accept='.png,.jpg,.jpeg,image/png,image/jpeg';
fileLabel.append(file);
const fromGenerated=el('button','studio-local-image-from-generated');
fromGenerated.className='secondary';fromGenerated.type='button';
actions.append(fileLabel,fromGenerated);
const canvas=el('canvas','studio-local-image-canvas');
canvas.hidden=true;canvas.style.cssText='display:block;width:auto;max-width:100%;max-height:440px;border-radius:12px;margin:12px auto';
canvas.setAttribute('role','img');
const controls=el('div','studio-local-image-controls');controls.className='row';
const channels=[
 ['brightness',50,150,100],
 ['contrast',50,150,100],
 ['saturate',0,200,100]
];
const sliders={};
for(const [key,min,max,initial] of channels){
 const label=el('label'),caption=el('span'),slider=el('input','studio-local-image-'+key);
 slider.type='range';slider.min=String(min);slider.max=String(max);slider.step='1';
 slider.value=String(initial);slider.disabled=true;
 slider.setAttribute('aria-label',key);label.append(caption,slider);controls.append(label);
 sliders[key]={caption,slider,initial};
}
const buttons=el('div');buttons.className='row';
const reset=el('button','studio-local-image-reset'),download=el('button','studio-local-image-download'),
 clear=el('button','studio-local-image-clear'),quick=el('button','studio-local-image-open');
for(const b of [reset,download,clear,quick]){b.type='button';b.className='secondary'}
buttons.append(reset,download,clear);
const notice=el('p','studio-local-image-status');notice.className='help';
notice.setAttribute('role','status');notice.setAttribute('aria-live','polite');
panel.append(summary,help,actions,controls,canvas,buttons,notice);
$('studio-imagegen-panel')?.after(panel);
if(!panel.parentNode)$('studio-compose').after(panel);
$('nexus-zen-suggestions').append(quick);
let original=null,source=null,epoch=0,loading=false,exporting=false,scope=null;
const MAX_BYTES=6_000_000,MAX_SIDE=4096,MAX_PIXELS=8_000_000;
const ident=()=>{
 const s=window.NexusStudioUI?.selection?.()||{};
 return JSON.stringify([s.projectId||null,s.threadId||null,s.head||null,s.revision||null,s.branchBase||null]);
};
function say(en,fa){notice.textContent=words(en,fa)}
function refresh(){
 const active=!!source,block=loading||exporting;
 file.disabled=block;fromGenerated.disabled=block; // Validate the source on click; an image may arrive later.
 for(const {slider} of Object.values(sliders))slider.disabled=block||!active;
 reset.disabled=block||!active;download.disabled=block||!active;clear.disabled=block||!active;
 canvas.hidden=!active;
}
function release(){
 epoch++;loading=false;exporting=false;if(original?.close)original.close();
 original=source=null;scope=null;
 canvas.width=canvas.height=0;
 file.value='';
 for(const {slider,initial} of Object.values(sliders))slider.value=String(initial);
 say('','');refresh();
}
function imageIsBounded(img){
 return Number.isFinite(img.width)&&Number.isFinite(img.height)&&
 img.width>0&&img.height>0&&img.width<=MAX_SIDE&&img.height<=MAX_SIDE&&
 img.width*img.height<=MAX_PIXELS;
}
function render(){
 if(!source)return;
 const ctx=canvas.getContext('2d',{alpha:true});
 if(!ctx||!('filter' in ctx)){release();say('This browser does not support local image filters.','این مرورگر از ویرایشگر محلی تصویر پشتیبانی نمی‌کند.');return}
 const b=sliders.brightness.slider.value,c=sliders.contrast.slider.value,s=sliders.saturate.slider.value;
 ctx.clearRect(0,0,canvas.width,canvas.height);
 ctx.filter='brightness('+b+'%) contrast('+c+'%) saturate('+s+'%)';
 ctx.drawImage(source,0,0,canvas.width,canvas.height);
 ctx.filter='none';
}
async function load(readImage){
 if(loading||exporting)return;
 const current=++epoch;
 loading=true;refresh();
 let bmp=null;
 try{
  bmp=await readImage();
  if(current!==epoch){bmp?.close?.();return}
  if(!bmp||!imageIsBounded(bmp))throw Error('dimensions');
  const ctx=canvas.getContext('2d',{alpha:true});
  if(!ctx||!('filter' in ctx))throw Error('unsupported');
  if(original?.close)original.close();
  original=bmp;source=bmp;scope=ident();
  canvas.width=bmp.width;canvas.height=bmp.height;
  for(const {slider,initial} of Object.values(sliders))slider.value=String(initial);
  render();
  say('Image loaded locally. The original file is unchanged; no upload occurred.',
      'تصویر روی دستگاه بارگذاری شد. فایل اصلی تغییر نکرد و هیچ ارسالی انجام نشد.');
 }catch{
  bmp?.close?.();
  if(current===epoch){release();say('Could not decode this image safely (PNG/JPEG, 6 MB, up to 8 megapixels).',
   'تصویر به‌شکل ایمن باز نشد؛ PNG/JPEG تا ۶ مگابایت و ۸ مگاپیکسل پذیرفته می‌شود.')}
 }finally{if(current===epoch)loading=false;refresh()}
}
file.addEventListener('change',()=>{
 const picked=file.files?.[0];
 if(!picked)return;
 if(!['image/png','image/jpeg'].includes(picked.type)||picked.size<=0||picked.size>MAX_BYTES){
  release();say('Choose a PNG/JPEG no larger than 6 MB.','فقط PNG/JPEG تا ۶ مگابایت انتخاب کن.');return;
 }
 load(()=>createImageBitmap(picked,{imageOrientation:'from-image'}));
});
fromGenerated.onclick=()=>{
 const preview=$('studio-imagegen-preview'),src=preview?.getAttribute('src');
 if(!src||!/^data:image\/(png|jpeg);base64,[A-Za-z0-9+/]+={0,2}$/.test(src)){
  say('No valid generated image is available.','تصویر تولیدشدهٔ معتبری موجود نیست.');return;
 }
 load(async()=>{
  const img=new Image();img.src=src;await img.decode();
  if(!img.naturalWidth||!img.naturalHeight)throw Error('empty');
  return await createImageBitmap(img);
 });
};
for(const {slider} of Object.values(sliders)){
 slider.addEventListener('input',()=>{if(source&&!loading&&!exporting)render()});
}
reset.onclick=()=>{
 for(const {slider,initial} of Object.values(sliders))slider.value=String(initial);
 if(source)render();
 say('Original appearance restored in the preview.','ظاهر اصلی در پیش‌نمایش بازگردانده شد.');
};
download.onclick=async()=>{
 if(!source||exporting||scope!==ident()){
  if(scope!==ident()){release();say('Conversation changed. Reopen the image to edit.','گفتگو تغییر کرده؛ تصویر را دوباره باز کن.')}
  return;
 }
 const current=epoch;exporting=true;refresh();
 try{
  render();
  const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
  if(!blob||blob.size>25_000_000)throw Error('export');
  if(epoch!==current||scope!==ident())return;
  const url=URL.createObjectURL(blob);
  try{
   const a=el('a');a.href=url;a.download='NEXUS-local-edit.png';
   document.body.append(a);a.click();a.remove();
  }finally{setTimeout(()=>URL.revokeObjectURL(url),30000)}
  say('Edited copy downloaded. Your original file was not changed.',
      'نسخهٔ ویرایش‌شده دریافت شد؛ فایل اصلی بدون تغییر باقی ماند.');
 }catch{if(epoch===current)say('Could not export this image.','خروجی گرفتن از تصویر ممکن نشد.')}
 finally{exporting=false;refresh()}
};
clear.onclick=release;
quick.onclick=()=>{panel.open=true;file.focus({preventScroll:true})};
function relabel(){
 summary.textContent=words('Edit an image locally (free)','ویرایش محلی تصویر (رایگان)');
 help.textContent=words(
  'No AI or network access. Adjust light, contrast and color without cropping. The original stays unchanged. Changes are never saved to chat history; download the edited copy to keep it.',
  'بدون مدل هوش مصنوعی و بدون ارسال اینترنتی. روشنایی، کنتراست و رنگ را بدون برش تنظیم کن. فایل اصلی تغییر نمی‌کند؛ برای نگه‌داری نسخهٔ ویرایش‌شده آن را دانلود کن.');
 fileLabel.firstChild?.nodeType===3&&fileLabel.firstChild.remove();
 fileLabel.insertBefore(document.createTextNode(words('Choose original image','انتخاب تصویر اصلی')),file);
 fromGenerated.textContent=words('Use last generated image','استفاده از تصویر ساخته‌شده');
 for(const [name,{caption}] of Object.entries(sliders))
  caption.textContent=({brightness:words('Brightness','روشنایی'),contrast:words('Contrast','کنتراست'),saturate:words('Saturation','اشباع رنگ')})[name];
 reset.textContent=words('Reset edits','بازنشانی تغییرات');
 download.textContent=words('Download edited PNG','دریافت PNG ویرایش‌شده');
 clear.textContent=words('Clear from this tab','پاک‌کردن از این برگه');
 quick.textContent=words('Edit image locally','ویرایش محلی تصویر');
}
let last=ident();
document.addEventListener('nexus-studio-state',()=>{const next=ident();if(next!==last){last=next;release()}refresh()});
document.addEventListener('nexus-studio-private-clear',release);
$('language')?.addEventListener('change',()=>queueMicrotask(relabel));
relabel();refresh();
})();
