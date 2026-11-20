/* Explicit provider reads. Review and attachment are separate actions. */
(()=>{'use strict';
const composer=$('nexus-zen-suggestions');
if(!composer)return;
const words=(en,fa)=>document.documentElement.lang==='fa'?fa:en;
const action=(id)=>{const b=el('button','');b.id=id;b.type='button';b.className='secondary';return b};
const open=action('studio-connections-open'),connect=action('studio-connections-load'),
 settings=action('studio-connections-settings'),read=action('studio-connections-read'),
 use=action('studio-connections-use'),close=action('studio-connections-close');
const dialog=el('dialog','');dialog.id='studio-connections';dialog.setAttribute('aria-labelledby','studio-connections-title');
const title=el('h2','');title.id='studio-connections-title';
const statusLine=el('p','');statusLine.setAttribute('role','status');
const operations=el('select',''),path=el('input',''),review=el('pre',''),result=el('pre','');
path.maxLength=300;path.placeholder='README.md';
const choices=[
 ['github.pulls','github','Open pull requests','درخواست‌های ادغام باز'],
 ['github.file','github','Read a file','خواندن فایل'],
 ['render.deploys','render','Recent deployments','انتشارهای اخیر']
];
dialog.append(title,connect,settings,close,operations,path,review,read,statusLine,result,use);
open.dataset.en='Connections';open.dataset.fa='اتصال‌ها';
document.body.append(dialog);composer.append(open);
let targets=[],origin='',controller=null,selectedResult=null;
function labels(){
 for(const [node,en,fa] of [
  [open,open.dataset.en,open.dataset.fa],[title,'Studio connections','اتصال‌های استودیو'],
  [connect,'Load connections','بارگیری اتصال‌ها'],[settings,'Gateway settings','تنظیمات درگاه'],
  [close,'Close','بستن'],[read,'Approve read','تأیید خواندن'],[use,'Attach to next message','پیوست به پیام بعدی']
 ])node.textContent=words(en,fa);
 operations.setAttribute('aria-label',words('Connection action','اقدام اتصال'));
 path.setAttribute('aria-label',words('Repository file path','مسیر فایل در مخزن'));
}
function clearResult(){selectedResult=null;result.textContent='';result.hidden=use.hidden=true}
function choice(){
 const action=choices.find(row=>row[0]===operations.value);
 return action?targets.find(x=>x.provider===action[1]):null;
}
function updateReview(){
 clearResult();
 const entry=choice();path.hidden=operations.value!=='github.file';
 read.hidden=review.hidden=!entry;
 read.disabled=Boolean(controller)||(!path.hidden&&!path.value.trim());
 review.textContent=entry?operations.selectedOptions[0].textContent+'\n'+entry.target+
  (path.hidden?'':' / '+path.value.trim()):'';
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
 const timer=setTimeout(()=>abort.abort(),15000);
 connect.disabled=read.disabled=true;
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
  const output=await boundedJson(response);
  if(controller!==abort||!dialog.open)return;
  if(url!==gateway()||token!==$('gateway-token').value.trim())throw Error('changed');
  statusLine.textContent='';apply(output,url);
 }catch{
  if(controller===abort){
   statusLine.textContent=words('Connection unavailable. Check the gateway, access token and provider permissions.',
    'اتصال برقرار نشد. درگاه، توکن دسترسی و مجوز سرویس را بررسی کن.');
  }
 }finally{
  clearTimeout(timer);
  if(controller===abort){controller=null;connect.disabled=false;read.disabled=!path.hidden&&!path.value.trim()}
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
  for(const [id,provider,en,fa] of choices)if(targets.some(x=>x.provider===provider)){
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
