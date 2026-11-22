/* Explicit provider review and separate approval. */
(()=>{'use strict';
const composer=$('nexus-zen-suggestions');
if(!composer)return;
const words=(en,fa)=>document.documentElement.lang==='fa'?fa:en;
const action=(id)=>{const b=el('button','');b.id=id;b.type='button';b.className='secondary';return b};
const open=action('studio-connections-open'),connect=action('studio-connections-load'),
 settings=action('studio-connections-settings'),read=action('studio-connections-read'),
 use=action('studio-connections-use'),close=action('studio-connections-close'),
 create=action('studio-connections-create'),preview=action('studio-file-preview'),
 view=action('studio-connections-view-chat');
const dialog=el('dialog','');dialog.id='studio-connections';dialog.setAttribute('aria-labelledby','studio-connections-title');
const title=el('h2','');title.id='studio-connections-title';
const statusLine=el('p','');statusLine.setAttribute('role','status');
const operations=el('select',''),path=el('input',''),review=el('pre',''),result=el('pre','');
path.id='studio-connection-path';path.maxLength=300;path.placeholder='README.md';
const topic=el('input',''),editor=el('textarea','');
topic.id='studio-file-topic';editor.id='studio-file-editor';topic.maxLength=48;topic.placeholder='example-change';editor.maxLength=24576;editor.rows=9;editor.dir='ltr';
const choices=[
 ['github.pulls','github','Open pull requests','درخواست‌های ادغام باز'],
 ['github.file','github','Read a file','خواندن فایل'],
 ['github.branch','github','Create a branch','ساخت شاخه'],
 ['github.edit','github','Edit a file','ویرایش فایل'],
 ['render.deploys','render','Recent deployments','انتشارهای اخیر']
];
dialog.append(title,connect,settings,close,operations,topic,path,review,read,editor,preview,statusLine,result,use,create,view);
view.hidden=true;
// Transient reviewed receipts live beside the active chat, never in session state.
const receipt=el('section','');receipt.id='studio-connection-receipt';receipt.hidden=true;
receipt.setAttribute('role','status');receipt.setAttribute('aria-live','polite');
const receiptTitle=el('strong',''),receiptStatus=el('p',''),receiptPreview=el('pre','');
const receiptAttach=action('studio-connection-attach'),receiptDismiss=action('studio-connection-dismiss'),
 receiptWitness=action('studio-connection-witness-export');
receipt.append(receiptTitle,receiptStatus,receiptPreview,receiptAttach,receiptWitness,receiptDismiss);
$('messages').after(receipt);
open.dataset.en='Connections';open.dataset.fa='اتصال‌ها';
document.body.append(dialog);composer.append(open);
let targets=[],origin='',controller=null,selectedResult=null,branchPlan=null,fileBase=null,filePlan=null,originalText='';
let requestedProvider=null,requestedOperation=null,dialogSelection=null,receiptCopy=null,receiptSelection=null;
let reviewedReadListener=null; // Single-use, ephemeral callback; not a provider attestation.
let pendingWitnessRequest=null; // In-memory, explicit user download only; never auto-uploaded.
function matchesSelection(selection){
 const current=window.NexusStudioUI.selection();
 return current.projectId===selection?.projectId&&current.threadId===selection?.threadId;
}
function clearReceipt(){
 receipt.hidden=view.hidden=true;receiptCopy=receiptSelection=null;
 pendingWitnessRequest=null;receiptWitness.hidden=true;
 receiptTitle.textContent=receiptStatus.textContent=receiptPreview.textContent='';
 receiptAttach.hidden=true;
}
function showReceipt({kind,operation='',target='',message='',body='',copy=null,witnessRequest=null}){
 clearReceipt();
 receiptSelection=dialogSelection;
 receiptTitle.textContent=([operation||'Connections',target].filter(Boolean).join(' · ')).slice(0,240);
 const success=kind==='read'||kind==='write';
 receiptStatus.textContent=message||(
  kind==='read'
   ?words('Approved read completed. External data is untrusted; not saved or sent to a model.',
           'خواندن تأییدشده انجام شد. دادهٔ خارجی غیرقابل‌اعتماد است؛ ذخیره یا به مدل ارسال نشده است.')
   :kind==='write'
   ?words('Provider confirmed the reviewed change. No merge or deployment was performed.',
           'سرویس، تغییر بازبینی‌شده را تأیید کرد. هیچ ادغام یا استقراری انجام نشده است.')
   :words('Request not confirmed. No successful operation is claimed.',
           'درخواست تأیید نشد. انجام موفق عملیات ادعا نمی‌شود.')
 );
 const text=String(body).slice(0,2400);
 receiptPreview.textContent=text+(String(body).length>2400?
  words('\n[Preview shortened. Full data remains in the reviewed dialog until closed.]',
        '\n[پیش‌نمایش کوتاه شده است؛ متن کامل تا زمان بستن در پنجرهٔ بازبینی موجود است.]'):'');
 receiptPreview.hidden=!text;
 receiptCopy=kind==='read'?copy:null;
 receiptAttach.hidden=!receiptCopy;
 pendingWitnessRequest=kind==='write'?witnessRequest:null;
 receiptWitness.hidden=!pendingWitnessRequest;
 receipt.hidden=false;view.hidden=!dialog.open;
 if(success)statusLine.textContent=words('Result is also available in Chat.','نتیجه در بخش گفتگو نیز نمایش داده شد.');
 // A workflow sees only a genuinely completed, consent-reviewed read. This
 // is a browser/gateway completion receipt, not independently signed evidence.
 if(kind==='read'&&reviewedReadListener?.operation===operation&&
    requestedOperation===operation&&matchesSelection(dialogSelection)){
  const listener=reviewedReadListener;reviewedReadListener=null;
  try{listener.callback(Object.freeze({operation,kind:'read',source:'studio-connection-response'}))}
  catch{/* An observer cannot invalidate the reviewed provider result. */}
 }
}
receiptDismiss.onclick=clearReceipt;
receiptWitness.onclick=()=>{
 if(!pendingWitnessRequest)return;
 if(!matchesSelection(receiptSelection)){clearReceipt();return}
 // Privacy boundary: no network, no clipboard, no background transfer.
 // The audit request holds source-only identifiers and SHA commitments.
 const blob=new Blob([JSON.stringify(pendingWitnessRequest,null,2)+'\n'],
  {type:'application/json'});
 const href=URL.createObjectURL(blob),anchor=document.createElement('a');
 anchor.href=href;anchor.download='nexus-github-audit-request.json';
 document.body.append(anchor);anchor.click();anchor.remove();
 setTimeout(()=>URL.revokeObjectURL(href),1000);
};
receiptAttach.onclick=()=>{
 if(!receiptCopy)return;
 if(!matchesSelection(receiptSelection)){clearReceipt();return}
 const {label,text}=receiptCopy;
 if(window.NexusStudioUI.stageChatContext(label,text)){
  receiptCopy=null;receiptAttach.hidden=true;
  receiptStatus.textContent=words('Attached to the next message, not sent. Review before sending.',
   'به پیام بعدی پیوست شد، اما ارسال نشده است. پیش از ارسال بازبینی کن.');
 }else receiptStatus.textContent=words('Open an active, unarchived chat with attachment capacity.',
  'گفتگوی فعال و آرشیونشده با ظرفیت پیوست باز کن.');
};
view.onclick=()=>{
 if(!discardFile())return;
 dialog.close();
 window.NexusStudioFocus?.openPanel('conversation-card');
 receipt.tabIndex=-1;receipt.focus({preventScroll:true});
};
document.addEventListener('nexus-studio-state',()=>{
 if(!receipt.hidden&&!matchesSelection(receiptSelection))clearReceipt();
 if(dialog.open&&!matchesSelection(dialogSelection)){
  dialog.close();
  reset();
 }
});
const branching=()=>operations.value==='github.branch',editing=()=>operations.value==='github.edit';
const validSha=s=>/^[a-f0-9]{40}$/.test(s);
function checkedWitnessRequest(response,operation,target,branch,revision,path=null){
 const q=response?.witness_request,r=response?.receipt;
 const expected=['authority','branch','external_witness_completed','file_path',
  'file_sha256','operation','provider','repository','review_reference_sha256',
  'revision','schema','source_receipt'];
 if(!q||typeof q!=='object'||Array.isArray(q)||
    Object.keys(q).length!==expected.length||expected.some(k=>!Object.hasOwn(q,k))||
    q.schema!=='nexus.studio.github.witness-request.v1'||q.provider!=='github'||
    q.authority!=='source_claim_only'||q.external_witness_completed!==false||
    q.operation!==operation||q.repository!==target||q.branch!==branch||
    q.revision!==revision||!/^[a-f0-9]{64}$/.test(q.review_reference_sha256)||
    q.file_path!==path||
    (path===null?q.file_sha256!==null:!/^[a-f0-9]{64}$/.test(q.file_sha256))||
    !r||typeof q.source_receipt!=='object'||Object.keys(q.source_receipt).length!==Object.keys(r).length||
    Object.keys(r).some(k=>q.source_receipt[k]!==r[k]))throw Error('unverified-witness-request');
 return q;
}
// A status object or GraphQL mutation response is not an execution receipt.
// Only the gateway's separately read-back, exact-revision result is accepted.
// This is same-provider verification, NOT independently signed attestation.
function verifiedWriteReceipt(response,operation,outcome,revision,fileBytes){
 const r=response?.receipt;
 return Boolean(r&&r.schema_version===1&&r.kind==='github_followup_read'&&
  r.operation===operation&&r.outcome===outcome&&r.revision===revision&&
  r.followup_read_verified===true&&r.reviewed_request_matched===true&&
  r.file_bytes_verified===fileBytes&&r.independent_attestation===false&&
  r.deployment_verified===false);
}
const discardFile=()=>!fileBase||editor.value===originalText||confirm(words('Discard the unsaved file edit?','ویرایش ذخیره‌نشدهٔ فایل پاک شود؟'));
function labels(){
 for(const [node,en,fa] of [
  [open,open.dataset.en,open.dataset.fa],[title,'Studio connections','اتصال‌های استودیو'],
  [connect,'Load connections','بارگیری اتصال‌ها'],[settings,'Gateway settings','تنظیمات درگاه'],
  [close,'Close','بستن'],[read,'Approve read','تأیید خواندن'],[create,'Confirm branch creation','تأیید ساخت شاخه'],[use,'Attach to next message','پیوست به پیام بعدی'],
  [view,'View result in chat','نمایش نتیجه در گفتگو'],[receiptAttach,'Attach to next message','پیوست به پیام بعدی'],
  [receiptWitness,'Export audit request','خروجی درخواست ممیزی'],[receiptDismiss,'Dismiss result','بستن نتیجه']
 ])node.textContent=words(en,fa);
 preview.textContent=words('Review changes','بازبینی تغییرات');
 topic.setAttribute('aria-label',words('Working branch suffix','نام کوتاه شاخهٔ کاری'));
 editor.setAttribute('aria-label',words('Replacement text','متن جایگزین فایل'));
 operations.setAttribute('aria-label',words('Connection action','اقدام اتصال'));
 path.setAttribute('aria-label',words('Repository file path','مسیر فایل در مخزن'));
}
function clearResult(){selectedResult=branchPlan=filePlan=null;result.textContent='';result.hidden=use.hidden=create.hidden=true}
function choice(){
 const action=choices.find(row=>row[0]===operations.value);
 return action?targets.find(x=>x.provider===action[1]):null;
}
function updateReview(){
 clearResult();fileBase=null;originalText=editor.value='';editor.hidden=preview.hidden=true;topic.hidden=!editing();
 const entry=choice(),branch=branching();path.hidden=!branch&&!editing()&&operations.value!=='github.file';
 path.placeholder=branch?'example-change':'README.md';
 path.setAttribute('aria-label',branch?words('New branch name','نام شاخهٔ جدید'):words('Repository file path','مسیر فایل در مخزن'));
 read.textContent=editing()?words('Load file','باز کردن فایل'):branch?words('Review branch','بازبینی شاخه'):words('Approve read','تأیید خواندن');
 read.hidden=review.hidden=!entry;
 read.disabled=Boolean(controller)||(!path.hidden&&!path.value.trim());
 review.textContent=entry?operations.selectedOptions[0].textContent+'\n'+entry.target+
  (path.hidden?'':' / '+(branch?'nexus/studio-':'')+path.value.trim()):'';
}
function setRequestControls(active){
 connect.disabled=create.disabled=preview.disabled=operations.disabled=topic.disabled=path.disabled=editor.readOnly=active;
 read.disabled=active||(!path.hidden&&!path.value.trim());
}
function reset(){
 controller?.abort();controller=null;targets=[];origin='';
 operations.replaceChildren();operations.hidden=true;
 statusLine.textContent='';topic.value=path.value='';updateReview();
 setRequestControls(false);
}
async function request(suffix,body,apply){
 if(controller||!dialog.open)return;
 clearReceipt();
 const abort=new AbortController();controller=abort;
 const branchWrite=suffix==='/github/branch',fileWrite=suffix==='/github/file-commit';
 const timer=setTimeout(()=>abort.abort(),suffix.includes('/file-')?55000:branchWrite?43000:15000);
 setRequestControls(true);
 statusLine.textContent=words('Loading…','در حال بارگیری…');
 try{
  const url=gateway(),token=$('gateway-token').value.trim();
  if(!token)throw Error('auth');
  if(body&&url!==origin)throw Error('changed');
  const response=await fetch(url+'/studio-api/connections'+suffix,{
   method:body?'POST':'GET',credentials:'omit',cache:'no-store',redirect:'error',
   headers:{authorization:'Bearer '+token,...(body?{'content-type':'application/json'}:{})},
   ...(body?{body:JSON.stringify(body)}:{}),signal:abort.signal
  });
  if(controller!==abort||!dialog.open)return;
  if(suffix.includes('/file-')&&response.status===409){
   clearResult();
   statusLine.textContent=words('Review again. Reload the file if the branch changed.','دوباره بازبینی کن. اگر شاخه تغییر کرده، فایل را دوباره باز کن.');
   showReceipt({kind:'error',operation:operations.value,message:statusLine.textContent});
   return;
  }
  if(branchWrite&&response.status===409){
   clearResult();
   statusLine.textContent=words('Review again or choose a new name. The branch was not confirmed.',
    'دوباره بازبینی کن یا نام دیگری انتخاب کن. ایجاد شاخه تأیید نشد.');
   showReceipt({kind:'error',operation:operations.value,message:statusLine.textContent});
   return;
  }
  const output=await boundedJson(response);
  if(controller!==abort||!dialog.open)return;
  if(url!==gateway()||token!==$('gateway-token').value.trim())throw Error('changed');
  statusLine.textContent='';apply(output,url);
 }catch{
  if(controller===abort&&dialog.open){
   // A write may have happened before its read-back failed. Revoke the old
   // approval so clicking Confirm again cannot blindly repeat the mutation.
   if(branchWrite||fileWrite)clearResult();
   statusLine.textContent=words('Connection unavailable. Check the gateway, access token and provider permissions.',
    'اتصال برقرار نشد. درگاه، توکن دسترسی و مجوز سرویس را بررسی کن.');
   if(branchWrite)statusLine.textContent=words('Branch result unknown. Retry with the same name.',
    'نتیجهٔ ساخت شاخه مشخص نیست. با همان نام دوباره تلاش کن.');
   if(fileWrite)statusLine.textContent=words('Commit status unknown. Check the branch before retrying.','وضعیت ثبت تغییر مشخص نیست. پیش از تلاش دوباره، شاخه را بررسی کن.');
   showReceipt({kind:'error',operation:operations.value,message:statusLine.textContent});
  }
 }finally{
  clearTimeout(timer);
  if(controller===abort){controller=null;setRequestControls(false)}
 }
}
/* Provider and operation hints only choose the review surface. They never
 * load credentials, call a provider, approve a read, or perform a write.
 */
function openFor({provider=null,operation=null,onReadReceipt=null}={}){
 if(dialog.open||!([null,'github','render'].includes(provider))||
   (operation!==null&&!choices.some(row=>row[0]===operation&&(!provider||row[1]===provider)))||
   (onReadReceipt!==null&&
    (typeof onReadReceipt!=='function'||!['github.pulls','render.deploys'].includes(operation))))
   return false;
 clearReceipt();reset();requestedProvider=provider;requestedOperation=operation;
 reviewedReadListener=onReadReceipt?{operation,callback:onReadReceipt}:null;
 labels();
 if(provider){
  const name=provider==='github'?'GitHub':'Render';
  statusLine.textContent=words(name+' selected. Load connections to review available actions.',
    name+' انتخاب شد. برای بازبینی عملیات موجود، اتصال‌ها را بارگیری کن.');
 }
 dialogSelection=window.NexusStudioUI.selection();
 dialog.showModal();connect.focus();return true;
}
open.onclick=()=>openFor();
close.onclick=()=>{if(discardFile())dialog.close()};
dialog.addEventListener('cancel',event=>{if(!discardFile())event.preventDefault()});
// A close event may be delivered after another review has already opened.
// Never let the previous dialog lifecycle erase the newly opened operation.
dialog.addEventListener('close',()=>{
 if(dialog.open)return;
 reviewedReadListener=null;requestedProvider=requestedOperation=dialogSelection=null;reset()
});
settings.onclick=()=>{
 if(!discardFile())return;
 dialog.close();document.dispatchEvent(new Event('nexus-studio-show-chat-options'));
 $('studio-model-settings').open=true;$('gateway').focus();
};
connect.onclick=()=>{
 if(!discardFile())return;
 reset();request('',null,(output,url)=>{
  if(!Array.isArray(output.connections))throw Error('catalog');
  targets=output.connections.filter(x=>typeof x.target==='string'&&/^[a-f0-9]{64}$/.test(x.configuration_id));
  origin=url;
  for(const [id,provider,en,fa] of choices)
   if((!requestedProvider||provider===requestedProvider)&&
      targets.some(x=>x.provider===provider&&(id!=='github.branch'||x.branch_creation===true)&&(id!=='github.edit'||x.file_commit===true))){
    operations.append(option(id,(provider==='github'?'GitHub':'Render')+' · '+words(en,fa)));
   }
  operations.hidden=!operations.options.length;
  if(requestedOperation){
   if([...operations.options].some(x=>x.value===requestedOperation))operations.value=requestedOperation;
   else {
    // A prohibited or unavailable operation must not silently fall back
    // to another action or another provider.
    operations.selectedIndex=-1;
    statusLine.textContent=words('This requested action is unavailable. Choose a permitted action explicitly.',
      'عملیات درخواستی در دسترس نیست. یک عملیات مجاز را صریحاً انتخاب کن.');
   }
  }
  if(operations.hidden)statusLine.textContent=words(
   'No configured connection for the requested provider on this gateway.',
   'برای سرویس درخواستی اتصالی روی این درگاه پیکربندی نشده است.');
  updateReview();
 });
};
operations.onchange=topic.onchange=path.onchange=()=>{
 if(controller)return;
 if(!discardFile()){operations.value='github.edit';topic.value=fileBase.slug;path.value=fileBase.path;preview.disabled=false;return}
 // The user may replace a preselected proposal, never approve it implicitly.
 if(document.activeElement===operations){requestedOperation=null;reviewedReadListener=null}
 clearReceipt();updateReview();
};
topic.oninput=path.oninput=()=>{
 if(controller)return;
 clearReceipt();
 if(fileBase){clearResult();preview.disabled=topic.value.trim()!==fileBase.slug||path.value.trim()!==fileBase.path;return}
 updateReview();
};
read.onclick=()=>{
 const entry=choice();if(!entry)return;
 if(editing()){
  const data={configuration_id:entry.configuration_id,slug:topic.value.trim(),path:path.value.trim()};
  if(!data.slug||!data.path||!discardFile())return;
  clearResult();
  request('/github/file-base',data,p=>{
   if(!sameFile(data,entry,p)||!validSha(p.base_sha)||typeof p.text!=='string')throw Error('file identity');
   fileBase={...data,base_sha:p.base_sha};
   clearResult();originalText=editor.value=p.text;editor.hidden=preview.hidden=false;
   review.textContent=p.target+' / '+p.branch+' / '+p.path+'\n'+p.base_sha;
   editor.focus();
  });
  return;
 }
 if(branching()){
  const slug=path.value.trim();
  if(!/^[a-z0-9][a-z0-9-]{1,46}[a-z0-9]$/.test(slug)){
   statusLine.textContent=words('Use 3–48 lowercase letters, digits or hyphens.','۳ تا ۴۸ حرف کوچک انگلیسی، عدد یا خط تیره وارد کن.');
   return;
  }
  const configuration_id=entry.configuration_id;
  clearResult();request('/github/branch-preview',{slug,configuration_id},p=>{
   if(p.target!==entry.target||p.branch!=='nexus/studio-'+slug||!/^[a-f0-9]{40}$/.test(p.base_sha)||
      !/^[a-f0-9]{64}$/.test(p.review_id)||!Number.isInteger(p.expires_at))throw Error('branch preview');
   branchPlan={slug,configuration_id,base_sha:p.base_sha,review_id:p.review_id,expires_at:p.expires_at};
   result.textContent=p.target+'\n'+p.branch+'\nmain @ '+p.base_sha;
   create.textContent=words('Confirm branch creation','تأیید ساخت شاخه');
   result.hidden=create.hidden=false;
  });
  return;
 }
 const body={consent:true,operation:operations.value,configuration_id:entry.configuration_id,
             ...(path.hidden?{}:{path:path.value.trim()})};
 clearResult();request('/read',body,(output)=>{
  if(output.provenance!=='external-untrusted'||output.operation!==body.operation||
     output.target!==entry.target||output.provider!==entry.provider)throw Error('source');
  const content=body.operation==='github.file'?output.result?.text:JSON.stringify(output.result,null,2);
  if(typeof content!=='string'||!content.trim())throw Error('empty');
  selectedResult={label:body.operation+' · '+(body.path||entry.target).slice(0,110),
                  text:'Source: '+entry.target+(body.path?' / '+body.path+' · '+output.result.blob_sha:'')+'\n\n'+content};
  result.textContent=selectedResult.text;
  result.hidden=use.hidden=false;
  showReceipt({kind:'read',operation:body.operation,target:entry.target,
    body:selectedResult.text,copy:{...selectedResult}});
 });
};
function sameFile(data,entry,p){
 return p.target===entry.target&&p.branch==='nexus/studio-'+data.slug&&p.path===data.path;
}
editor.oninput=()=>{if(!controller)clearResult()};
preview.onclick=()=>{
 if(!fileBase||topic.value.trim()!==fileBase.slug||path.value.trim()!==fileBase.path)return;
 const entry=choice(),data={...fileBase,text:editor.value};
 clearResult();request('/github/file-preview',data,p=>{
  if(!sameFile(data,entry,p)||p.base_sha!==data.base_sha||typeof p.diff!=='string'||
     !/^[a-f0-9]{64}$/.test(p.review_id)||!Number.isInteger(p.expires_at))throw Error('file review');
  filePlan={...data,review_id:p.review_id,expires_at:p.expires_at};
  result.textContent=p.diff;result.hidden=create.hidden=false;
  create.textContent=words('Confirm commit','تأیید ثبت تغییر');
 });
};
create.onclick=()=>{
 if(filePlan&&!controller){
  const approved=filePlan,entry=choice();
  request('/github/file-commit',{...approved,consent:true},p=>{
   if(!sameFile(approved,entry,p)||!validSha(p.commit)||
      !verifiedWriteReceipt(p,'github.file_commit','committed',p.commit,true))
    throw Error('commit follow-up proof missing');
   const witness=checkedWitnessRequest(p,'github.file_commit',entry.target,p.branch,p.commit,approved.path);
   clearResult();fileBase=null;originalText=editor.value='';editor.hidden=preview.hidden=true;
   result.textContent=words('Commit created','تغییر ثبت شد')+'\n'+p.commit;result.hidden=false;
   showReceipt({kind:'write',operation:'github.edit',target:entry.target,
     message:words('The reviewed file bytes and commit were re-read from GitHub. Not independently attested or deployed.',
       'بایت‌های فایل بازبینی‌شده و کامیت از گیت‌هاب دوباره خوانده شدند؛ گواهی مستقل یا استقرار تأیید نشده است.'),
     body:'Commit: '+p.commit+'\nWorking branch: '+p.branch,
     witnessRequest:witness});
  });
  return;
 }
 if(!branchPlan||controller)return;
 const approved=branchPlan,entry=choice();
 request('/github/branch',{...approved,consent:true},p=>{
  if(p.target!==entry.target||p.branch!=='nexus/studio-'+approved.slug||p.base_sha!==approved.base_sha||
     !['created','already_exists'].includes(p.status)||
     !verifiedWriteReceipt(p,'github.branch',p.status,approved.base_sha,false))
    throw Error('branch follow-up proof missing');
  const witness=checkedWitnessRequest(p,'github.branch',p.target,p.branch,p.base_sha);
  const label=p.status==='created'?words('Branch created','شاخه ساخته شد'):words('Branch already exists','شاخه از قبل وجود داشت');
  clearResult();result.textContent=label+'\n'+p.target+' / '+p.branch;result.hidden=false;
  showReceipt({kind:'write',operation:'github.branch',target:p.target,
    message:p.status==='created'?words('Reviewed branch was created and re-read at the matching SHA. Not independently attested or deployed.',
      'شاخه ساخته و با شناسهٔ بازبینی‌شده دوباره خوانده شد؛ گواهی مستقل یا استقرار تأیید نشده است.'):
      words('Existing branch was re-read at the matching SHA. No new branch was created.',
      'شاخهٔ موجود با شناسهٔ بازبینی‌شده دوباره خوانده شد؛ شاخهٔ تازه‌ای ساخته نشد.'),
    body:'Branch: '+p.branch+'\nBase: '+p.base_sha,
    witnessRequest:witness});
 });
};
use.onclick=()=>{
 if(!selectedResult||controller)return;
 const {label,text}=selectedResult;
 if(window.NexusStudioUI.stageChatContext(label,text)){
  receiptCopy=null;receiptAttach.hidden=true;
  receiptStatus.textContent=words('Attached to next message; not sent to a model.',
    'به پیام بعدی پیوست شد؛ به مدل ارسال نشده است.');
  dialog.close();$('message').focus()
 }
 else statusLine.textContent=words('Open an active chat with room for attachments.','یک گفتگوی فعال با ظرفیت پیوست باز کن.');
};
window.addEventListener('beforeunload',event=>{
 if(fileBase&&editor.value!==originalText){event.preventDefault();event.returnValue=''}
});
document.addEventListener('nexus-studio-private-clear',()=>{
 reviewedReadListener=null;clearReceipt();if(dialog.open)dialog.close();reset()
});
for(const id of ['gateway','gateway-token'])$(id).addEventListener('input',()=>{
 reviewedReadListener=null;clearReceipt();reset()
});
$('language').addEventListener('change',labels);
window.NexusStudioConnections=Object.freeze({openFor});
labels();
})();
