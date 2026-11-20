/* Explicit provider review and separate approval. */
(()=>{'use strict';
const composer=$('nexus-zen-suggestions');
if(!composer)return;
const words=(en,fa)=>document.documentElement.lang==='fa'?fa:en;
const action=(id)=>{const b=el('button','');b.id=id;b.type='button';b.className='secondary';return b};
const open=action('studio-connections-open'),connect=action('studio-connections-load'),
 settings=action('studio-connections-settings'),read=action('studio-connections-read'),
 use=action('studio-connections-use'),close=action('studio-connections-close'),
 create=action('studio-connections-create');
const dialog=el('dialog','');dialog.id='studio-connections';dialog.setAttribute('aria-labelledby','studio-connections-title');
const title=el('h2','');title.id='studio-connections-title';
const statusLine=el('p','');statusLine.setAttribute('role','status');
const operations=el('select',''),path=el('input',''),review=el('pre',''),result=el('pre','');
path.maxLength=300;path.placeholder='README.md';
const choices=[
 ['github.pulls','github','Open pull requests','درخواست‌های ادغام باز'],
 ['github.file','github','Read a file','خواندن فایل'],
 ['github.branch','github','Create a branch','ساخت شاخه'],
 ['render.deploys','render','Recent deployments','انتشارهای اخیر']
];
dialog.append(title,connect,settings,close,operations,path,review,read,statusLine,result,use,create);
open.dataset.en='Connections';open.dataset.fa='اتصال‌ها';
document.body.append(dialog);composer.append(open);
let targets=[],origin='',controller=null,selectedResult=null,branchPlan=null;
const branching=()=>operations.value==='github.branch';
function labels(){
 for(const [node,en,fa] of [
  [open,open.dataset.en,open.dataset.fa],[title,'Studio connections','اتصال‌های استودیو'],
  [connect,'Load connections','بارگیری اتصال‌ها'],[settings,'Gateway settings','تنظیمات درگاه'],
  [close,'Close','بستن'],[read,'Approve read','تأیید خواندن'],[create,'Confirm branch creation','تأیید ساخت شاخه'],[use,'Attach to next message','پیوست به پیام بعدی']
 ])node.textContent=words(en,fa);
 operations.setAttribute('aria-label',words('Connection action','اقدام اتصال'));
 path.setAttribute('aria-label',words('Repository file path','مسیر فایل در مخزن'));
}
function clearResult(){selectedResult=branchPlan=null;result.textContent='';result.hidden=use.hidden=create.hidden=true}
function choice(){
 const action=choices.find(row=>row[0]===operations.value);
 return action?targets.find(x=>x.provider===action[1]):null;
}
function updateReview(){
 clearResult();
 const entry=choice(),branch=branching();path.hidden=!branch&&operations.value!=='github.file';
 path.placeholder=branch?'example-change':'README.md';
 path.setAttribute('aria-label',branch?words('New branch name','نام شاخهٔ جدید'):words('Repository file path','مسیر فایل در مخزن'));
 read.textContent=branch?words('Review branch','بازبینی شاخه'):words('Approve read','تأیید خواندن');
 read.hidden=review.hidden=!entry;
 read.disabled=Boolean(controller)||(!path.hidden&&!path.value.trim());
 review.textContent=entry?operations.selectedOptions[0].textContent+'\n'+entry.target+
  (path.hidden?'':' / '+(branch?'nexus/studio-':'')+path.value.trim()):'';
}
function reset(){
 controller?.abort();controller=null;targets=[];origin='';
 operations.replaceChildren();operations.hidden=true;
 statusLine.textContent='';updateReview();
 connect.disabled=false;
}
async function request(suffix,body,apply){
 if(controller)return;
 const abort=new AbortController();controller=abort;
 const branchWrite=suffix==='/github/branch';
 const timer=setTimeout(()=>abort.abort(),branchWrite?43000:15000);
 connect.disabled=read.disabled=create.disabled=true;
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
  if(branchWrite&&response.status===409){
   statusLine.textContent=words('Review again or choose a new name. The branch was not confirmed.',
    'دوباره بازبینی کن یا نام دیگری انتخاب کن. ایجاد شاخه تأیید نشد.');
   return;
  }
  const output=await boundedJson(response);
  if(controller!==abort||!dialog.open)return;
  if(url!==gateway()||token!==$('gateway-token').value.trim())throw Error('changed');
  statusLine.textContent='';apply(output,url);
 }catch{
  if(controller===abort){
   statusLine.textContent=words('Connection unavailable. Check the gateway, access token and provider permissions.',
    'اتصال برقرار نشد. درگاه، توکن دسترسی و مجوز سرویس را بررسی کن.');
   if(branchWrite)statusLine.textContent=words('Branch result unknown. Retry with the same name.',
    'نتیجهٔ ساخت شاخه مشخص نیست. با همان نام دوباره تلاش کن.');
  }
 }finally{
  clearTimeout(timer);
  if(controller===abort){controller=null;connect.disabled=create.disabled=false;read.disabled=!path.hidden&&!path.value.trim()}
 }
}
open.onclick=()=>{reset();labels();dialog.showModal()};
close.onclick=()=>dialog.close();
dialog.addEventListener('close',reset);
settings.onclick=()=>{
 dialog.close();document.dispatchEvent(new Event('nexus-studio-show-chat-options'));
 $('studio-model-settings').open=true;$('gateway').focus();
};
connect.onclick=()=>{
 reset();request('',null,(output,url)=>{
  if(!Array.isArray(output.connections))throw Error('catalog');
  targets=output.connections.filter(x=>typeof x.target==='string'&&/^[a-f0-9]{64}$/.test(x.configuration_id));
  origin=url;
  for(const [id,provider,en,fa] of choices)if(targets.some(x=>x.provider===provider&&(id!=='github.branch'||x.branch_creation===true))){
   operations.append(option(id,(provider==='github'?'GitHub':'Render')+' · '+words(en,fa)));
  }
  operations.hidden=!operations.options.length;
  if(operations.hidden)statusLine.textContent=words('No connections configured on this gateway.','اتصالی روی این درگاه تنظیم نشده است.');
  updateReview();
 });
};
operations.onchange=path.oninput=()=>{controller?.abort();controller=null;connect.disabled=false;updateReview()};
read.onclick=()=>{
 const entry=choice();if(!entry)return;
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
 });
};
create.onclick=()=>{
 if(!branchPlan||controller)return;
 const approved=branchPlan,entry=choice();
 request('/github/branch',{...approved,consent:true},p=>{
  if(p.target!==entry.target||p.branch!=='nexus/studio-'+approved.slug||p.base_sha!==approved.base_sha||
     !['created','already_exists'].includes(p.status))throw Error('branch identity');
  const label=p.status==='created'?words('Branch created','شاخه ساخته شد'):words('Branch already exists','شاخه از قبل وجود داشت');
  clearResult();result.textContent=label+'\n'+p.target+' / '+p.branch;result.hidden=false;
 });
};
use.onclick=()=>{
 if(!selectedResult||controller)return;
 const {label,text}=selectedResult;
 if(window.NexusStudioUI.stageChatContext(label,text)){dialog.close();$('message').focus()}
 else statusLine.textContent=words('Open an active chat with room for attachments.','یک گفتگوی فعال با ظرفیت پیوست باز کن.');
};
document.addEventListener('nexus-studio-private-clear',()=>{if(dialog.open)dialog.close();reset()});
for(const id of ['gateway','gateway-token'])$(id).addEventListener('input',reset);
$('language').addEventListener('change',labels);
labels();
})();
