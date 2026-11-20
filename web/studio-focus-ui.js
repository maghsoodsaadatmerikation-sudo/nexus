/* NEXUS Studio: opt-out chat-first mobile navigation; presentation-only. */
(()=>{'use strict';
const $=id=>document.getElementById(id),media=matchMedia('(max-width:780px)');
const targets=[
  ['conversation-card','chat','Chat','گفتگو'],
  ['projects-card','projects','Projects','پروژه‌ها'],
  ['vault-card','save','Save','ذخیره']
];
const tools=[
  ['canvas-card','Writing','نوشتن','¶','Draft and revisit versions','پیش‌نویس و بازبینی نسخه‌ها'],
  ['research-card','Research','پژوهش','⌕','Look up public sources','جست‌وجوی منابع عمومی'],
  ['music-card','Music Lab','موسیقی','♪','Compose and export WAV or MIDI','آهنگ‌سازی و خروجی WAV یا MIDI'],
  ['orchestra-card','Orchestra & vocal','ارکستر و آواز','♫','Arrange and mix your vocal','تنظیم ارکستر و میکس وکال'],
  ['data-card','Data analysis','تحلیل داده','∑','Summarize CSV and JSON','خلاصه‌سازی CSV و JSON'],
  ['chart-card','Charts','نمودارها','▥','Draw charts and export PNG','رسم نمودار و خروجی PNG'],
  ['sources-card','Sources','منابع','▤','Find text in your files','یافتن متن در فایل‌های پروژه'],
  ['profile-card','Assistant & memory','دستیار و حافظه','◎','Set project preferences','تنظیم ترجیحات پروژه'],
  ['code-card','Code','کدنویسی','‹›','Run reviewed JavaScript','اجرای JavaScript بازبینی‌شده'],
  ['reminders-card','Reminders','یادآورها','◷','Export a calendar reminder','خروجی یادآور برای تقویم'],
  ['tasks-card','Tasks','کارها','▦','Run a reviewed task plan','اجرای برنامهٔ بازبینی‌شدهٔ کارها'],
  ['astrology-card','Astrology','اخترشناسی','✧','Explore charts and transits','بررسی چارت و گذرها'],
  ['sky-card','Sky','آسمان','◐','Inspect local sky calculations','بررسی محاسبات آسمان']
];
const sections=[...targets.map(x=>x[0]),...tools.map(x=>x[0])];
if(sections.some(id=>!$(id))||!$('language')||!$('conversation-card'))return;
const main=document.querySelector('body>main');
const nav=document.createElement('nav');nav.id='studio-focus-nav';nav.setAttribute('aria-label','Primary Studio navigation');
const toggle=document.createElement('button');toggle.id='studio-focus-toggle';toggle.type='button';toggle.className='secondary';
const catalog=document.createElement('button');catalog.id='studio-tools-toggle';catalog.type='button';
catalog.setAttribute('aria-controls','studio-focus-tools');
const top=document.createElement('div');top.id='studio-focus-top';top.append(catalog,toggle);
const toolsTray=document.createElement('div');toolsTray.id='studio-focus-tools';toolsTray.hidden=true;
toolsTray.setAttribute('role','group');toolsTray.setAttribute('aria-label','Studio tools');
const toolHeading=document.createElement('h2');toolHeading.id='studio-focus-tools-title';
const search=document.createElement('input');search.id='studio-tool-search';search.type='search';
const noTools=document.createElement('p');noTools.className='help';noTools.hidden=true;noTools.setAttribute('role','status');
const toolsGrid=document.createElement('div');toolsGrid.className='studio-focus-tools-grid';
toolsTray.append(toolHeading,search,toolsGrid,noTools);
const onboarding=document.createElement('div');onboarding.id='studio-focus-onboarding';onboarding.className='studio-focus-onboarding';
onboarding.setAttribute('role','group');onboarding.setAttribute('aria-label','Getting started');
const hint=document.createElement('p'),start=document.createElement('button');start.type='button';
const tryTools=document.createElement('button');tryTools.type='button';tryTools.className='secondary';
onboarding.append(hint,start,tryTools);
$('conversation-card').insertBefore(onboarding,$('conversation-card').children[1]||null);
const existingNav=document.querySelector('nav.tool-nav');existingNav.before(top,toolsTray);main.append(nav);
document.documentElement.classList.add('studio-enhanced');
const labels=[
  ['conversation-card','Chat','گفتگو','◫'],
  ['projects-card','Projects','پروژه‌ها','▤'],
  ['tools','Tools','ابزارها','▦'],
  ['vault-card','Save','ذخیره','◇']
];
const labelsToRefresh=[];
function labelButton(button,icon,en,fa,descriptionEn='',descriptionFa=''){
 const symbol=document.createElement('span');symbol.className='studio-control-icon';symbol.textContent=icon;
 symbol.setAttribute('aria-hidden','true');
 const label=document.createElement('span');label.className='studio-control-label';
 const title=document.createElement('span');label.append(title);
 const detail=document.createElement('small');
 if(descriptionEn)label.append(detail);
 button.append(symbol,label);
 labelsToRefresh.push(()=>{title.textContent=words(en,fa);detail.textContent=words(descriptionEn,descriptionFa)});
}
for(const [id,en,fa,icon] of labels){
 const button=document.createElement('button');button.type='button';button.className='studio-focus-tab';
 button.dataset.panel=id;
 labelButton(button,icon,en,fa);
 button.setAttribute('aria-controls',id==='tools'?'studio-focus-tools':id);
 button.addEventListener('click',()=>id==='tools'?openTools():openPanel(id));
 nav.append(button);
}
for(const [id,en,fa,icon,descriptionEn,descriptionFa] of tools){
 const button=document.createElement('button');button.type='button';
 button.dataset.panel=id;
 labelButton(button,icon,en,fa,descriptionEn,descriptionFa);
 labelsToRefresh.push(()=>button.setAttribute('aria-label',words(en,fa)));
 button.setAttribute('aria-controls',id);
 button.addEventListener('click',()=>openPanel(id));toolsGrid.append(button);
}
let selected='conversation-card',focused=true,manual=false,toolsOpen=false;
const isFa=()=>document.documentElement.lang==='fa';
const words=(en,fa)=>isFa()?fa:en;
const normalize=value=>value.toLowerCase().replace(/[يى]/g,'ی').replace(/ك/g,'ک').replace(/\u200c/g,' ').trim();
function filterTools(){
 const query=normalize(search.value).split(/\s+/).filter(Boolean);
 let results=0;
 for(const [index,tool] of tools.entries()){
  const text=normalize([...tool.slice(1,3),...tool.slice(4)].join(' '));
  const visible=query.every(word=>text.includes(word));
  toolsGrid.children[index].hidden=!visible;
  if(visible)results++;
 }
 noTools.hidden=results!==0;
}
function refreshLabels(){
 toggle.textContent=focused?words('Show all sections','نمایش همهٔ بخش‌ها'):words('Focus on one section','تمرکز بر یک بخش');
 toggle.setAttribute('aria-pressed',String(focused));
 nav.setAttribute('aria-label',words('Primary Studio navigation','ناوبری اصلی نکسوس'));
 toolsTray.setAttribute('aria-label',words('Studio tools','ابزارهای نکسوس'));
 onboarding.setAttribute('aria-label',words('Getting started','شروع کار'));
 toolHeading.textContent=words('Choose a tool','انتخاب ابزار');
 catalog.textContent=toolsOpen?words('Close tools','بستن ابزارها'):words('Browse tools','دیدن ابزارها');
 catalog.setAttribute('aria-expanded',String(toolsOpen));
 search.placeholder=words('Search tools','جست‌وجوی ابزار');
 search.setAttribute('aria-label',search.placeholder);
 noTools.textContent=words('No tools match your search.','ابزاری با این جست‌وجو پیدا نشد.');
 tryTools.textContent=words('Browse tools','دیدن ابزارها');
 labelsToRefresh.forEach(update=>update());
}
function layout(){
 document.documentElement.classList.toggle('studio-focus-mode',focused);
 nav.hidden=!focused;toolsTray.hidden=!toolsOpen;
 for(const id of sections)$(id).hidden=focused&&(toolsOpen||id!==selected);
 const category=toolsOpen||tools.some(x=>x[0]===selected)?'tools':selected;
 for(const button of nav.querySelectorAll('button')){
  const active=focused&&button.dataset.panel===category;
  button.setAttribute('aria-current',active?'page':'false');
 }
 refreshLabels();refreshOnboarding();syncTyping();requestAnimationFrame(syncTyping);
}
function moveTo(element){
 if(!focused)return;
 element.scrollIntoView({block:'start',behavior:'instant'});
}
function openPanel(id){
 if(!sections.includes(id))return false;
 selected=id;toolsOpen=false;layout();$(id).scrollIntoView({block:'start',behavior:'instant'});
 const heading=$(id).querySelector('h2');if(heading){heading.tabIndex=-1;heading.focus({preventScroll:true})}
 return true;
}
function openTools(){
 if(!toolsOpen){search.value='';filterTools()}
 toolsOpen=true;layout();toolsTray.scrollIntoView({block:'start',behavior:'instant'});
 toolHeading.tabIndex=-1;toolHeading.focus({preventScroll:true});
}
function setFocus(on,explicit=false){
 if(explicit)manual=true;
 focused=Boolean(on);if(!focused)toolsOpen=false;
 layout();
 document.dispatchEvent(new Event('nexus-studio-chat-layout'));
 if(focused)moveTo(toolsOpen?toolsTray:$(selected));
}
function refreshOnboarding(){
 let state=null;try{state=window.NexusStudioUI?.snapshot()}catch{}
 const projects=state?.projects||[];
 const selectedProject=projects.find(p=>p.id===$('projects').value);
 const hasThread=selectedProject?.threads?.some(t=>!t.archived);
 const visible=!projects.length||!hasThread;
 onboarding.hidden=!visible;
 if(!visible)return;
 const create=projects.length===0;
 hint.textContent=create
  ?words('Chat, research, analyze files or make music. No account needed.',
         'گفتگو کن، پژوهش کن، فایل تحلیل کن یا موسیقی بساز. نیازی به حساب کاربری نیست.')
  :words('Write a message or start a conversation. The local guide is not a generative AI model.',
         'پیامت را بنویس یا گفتگو را آغاز کن. راهنمای محلی مدل هوش مصنوعی مولد نیست.');
 start.textContent=words('Start chatting','شروع گفتگو');
 start.onclick=()=>{
  if(!window.NexusStudioUI?.startConversation())return;
  openPanel('conversation-card');$('message').focus({preventScroll:true});
 };
}
toggle.addEventListener('click',()=>setFocus(!focused,true));
catalog.addEventListener('click',()=>toolsOpen?openPanel(selected):openTools());
tryTools.addEventListener('click',openTools);
search.addEventListener('input',filterTools);
media.addEventListener('change',()=>{if(!manual)setFocus(true)});
existingNav.addEventListener('click',event=>{
 if(!focused)return;
 const anchor=event.target.closest('a[href^="#"]');
 if(!anchor||!existingNav.contains(anchor))return;
 const id=anchor.getAttribute('href').slice(1);
 if(sections.includes(id)){event.preventDefault();openPanel(id)}
});
const observer=new MutationObserver(()=>refreshOnboarding());
observer.observe($('projects'),{childList:true});
observer.observe($('history'),{childList:true});
$('language').addEventListener('change',()=>queueMicrotask(()=>{refreshLabels();refreshOnboarding()}));
document.addEventListener('nexus-studio-open-chat',()=>openPanel('conversation-card'));
document.addEventListener('keydown',event=>{
 if(event.key!=='Escape'||!toolsOpen||!toolsTray.contains(document.activeElement))return;
 event.preventDefault();
 if(search.value){search.value='';filterTools();return}
 openPanel(selected);
});
function openLinkedPanel(){if(location.hash)openPanel(location.hash.slice(1))}
window.addEventListener('hashchange',openLinkedPanel);
const textControls='input:not([type="checkbox"]):not([type="radio"]),textarea,select';
function syncTyping(){
 const active=document.activeElement;
 document.documentElement.classList.toggle('studio-focus-typing',Boolean(active?.matches?.(textControls)));
}
document.addEventListener('focusin',syncTyping);
document.addEventListener('focusout',()=>queueMicrotask(syncTyping));
window.NexusStudioFocus={openPanel,openTools,setFocus,isFocused:()=>focused,active:()=>toolsOpen?'tools':selected};
layout();
openLinkedPanel();
})();


/* NEXUS Zen: conversation is the home on every screen. */
(()=>{'use strict';
const $=id=>document.getElementById(id),focus=window.NexusStudioFocus;
if(!focus||!$('studio-focus-top'))return;
document.documentElement.classList.add('nexus-zen-active');
const tr=(en,fa)=>document.documentElement.lang==='fa'?fa:en;
const make=(id,label)=>{const x=document.createElement('button');x.type='button';x.id=id;x.className='secondary';x.textContent=label;return x};
const bar=document.createElement('div');bar.id='nexus-zen-bar';
const menu=make('nexus-zen-menu','☰'),home=make('nexus-zen-home','NEXUS'),newChat=make('nexus-zen-new','＋'),all=make('nexus-zen-tools','✦');
menu.setAttribute('aria-controls','nexus-zen-drawer');menu.setAttribute('aria-expanded','false');
const safety=document.createElement('small');safety.id='nexus-zen-storage-indicator';home.append(safety);
bar.append(menu,home,newChat,all);$('studio-focus-top').prepend(bar);
const shade=document.createElement('div'),drawer=document.createElement('aside');
shade.id='nexus-zen-shade';drawer.id='nexus-zen-drawer';shade.hidden=drawer.hidden=true;
drawer.setAttribute('role','dialog');drawer.setAttribute('aria-modal','true');
const header=document.createElement('div');header.className='nexus-zen-drawer-head';
const title=document.createElement('strong'),close=make('nexus-zen-close','×');
header.append(title,close);
const find=document.createElement('input');find.type='search';find.maxLength=200;find.id='nexus-zen-find';
const archiveLabel=document.createElement('label');archiveLabel.className='nexus-zen-archived';
const archiveToggle=document.createElement('input');archiveToggle.id='nexus-zen-archived';archiveToggle.type='checkbox';
const archiveWords=document.createElement('span');archiveLabel.append(archiveToggle,archiveWords);
const history=document.createElement('div');history.id='nexus-zen-history';
const actions=document.createElement('div');actions.className='nexus-zen-links';
const nav=[['projects-card','Projects','پروژه‌ها'],['vault-card','Private archive','آرشیو خصوصی'],['profile-card','Preferences & memory','ترجیحات و حافظه']];
const links=nav.map(([id,en,fa])=>{const b=make('nexus-zen-'+id,'');b.addEventListener('click',()=>go(id));actions.append(b);return [b,en,fa]});
const full=make('nexus-zen-full','');full.addEventListener('click',()=>{dismiss();focus.setFocus(false,true)});actions.append(full);
drawer.append(header,find,archiveLabel,history,actions);document.body.append(shade,drawer);
let restore=null;
function dismiss(){if(drawer.hidden)return;drawer.hidden=shade.hidden=true;menu.setAttribute('aria-expanded','false');restore?.focus?.({preventScroll:true})}
function show(){restore=document.activeElement;drawer.hidden=shade.hidden=false;menu.setAttribute('aria-expanded','true');render();find.focus()}
function go(id){dismiss();focus.openPanel(id)}
function start(){
 dismiss();
 if(!window.NexusStudioUI?.startConversation(true))return;
 go('conversation-card');$('message').focus({preventScroll:true});
}
function render(){
 history.replaceChildren();
 const state=window.NexusStudioUI?.snapshot?.(),q=find.value.trim().toLocaleLowerCase();
 let n=0;
 // Inspect session state directly. The old hidden history pane may be filtered,
 // so it must not be the source of truth for the chat drawer.
 for(const project of [...(state?.projects||[])].reverse()){
  for(const thread of [...(project.threads||[])].reverse()){
   if(thread.isolated||(thread.archived&&!archiveToggle.checked))continue;
   const texts=thread.nodes||[];
   const preview=(texts.find(x=>x.role==='user')?.text||'').replace(/\s+/g,' ').trim().slice(0,72);
   if(q&&![project.title,thread.title].some(x=>x.toLocaleLowerCase().includes(q))&&
      !texts.some(x=>typeof x.text==='string'&&x.text.toLocaleLowerCase().includes(q)))continue;
   const b=make('',preview&&/^(New conversation|گفتگوی جدید)$/i.test(thread.title)?preview:thread.title);
   b.removeAttribute('id');b.className='nexus-zen-chat-result';
   const detail=document.createElement('small');
   detail.textContent=project.title+(thread.archived?' · '+tr('Archived','آرشیوشده'):'');
   b.append(detail);
   const selection=window.NexusStudioUI?.selection?.();
   b.setAttribute('aria-current',thread.id===selection?.threadId&&project.id===selection?.projectId?'page':'false');
   b.addEventListener('click',()=>{
    if(window.NexusStudioUI?.openConversation?.(project.id,thread.id))go('conversation-card');
   });
   history.append(b);n++;if(n>=80)break;
  }
  if(n>=80)break;
 }
 if(!n){const p=document.createElement('p');p.className='help';p.textContent=tr('No matching conversations in this local session.','گفتگوی مطابقی در این نشست محلی نیست.');history.append(p)}
 else if(n>=80){const p=document.createElement('p');p.className='help';p.textContent=tr('Showing 80 conversations. Narrow the search to find more.','۸۰ گفتگو نمایش داده شده؛ برای یافتن موارد بیشتر جست‌وجو را دقیق‌تر کن.');history.append(p)}
}
function refreshSafety(){
 const s=window.NexusStudioUI?.uiStatus?.();
 if(!s)return;
 const unsaved=Boolean(s.lossRisk||s.dirty||s.unsavedForms||s.unsavedLocalMedia);
 safety.textContent=unsaved?tr('Unsaved changes','تغییرات ذخیره‌نشده'):
  s.vaultUnlocked?tr('Archive unlocked','آرشیو باز است'):tr('Temporary · not saved','موقت · ذخیره‌نشده');
 safety.dataset.unsaved=String(unsaved);
 home.setAttribute('aria-label',tr('Back to chat: ','بازگشت به گفتگو: ')+safety.textContent);
}
function labels(){
 title.textContent=tr('Conversations','گفتگوها');find.placeholder=tr('Search conversations','جست‌وجوی گفتگوها');find.setAttribute('aria-label',find.placeholder);
 archiveWords.textContent=tr('Show archived','نمایش گفتگوهای آرشیوشده');
 archiveToggle.setAttribute('aria-label',archiveWords.textContent);
 drawer.setAttribute('aria-label',tr('Conversations and settings','گفتگوها و تنظیمات'));
 for(const [b,en,fa] of links)b.textContent=tr(en,fa);
 full.textContent=tr('Advanced workspace','نمایش همهٔ بخش‌ها');
 for(const [b,en,fa] of [[menu,'Menu','منو'],[home,'Back to chat','بازگشت به گفتگو'],[newChat,'New conversation','گفتگوی جدید'],[all,'Capabilities','قابلیت‌ها'],[close,'Close menu','بستن منو']])b.setAttribute('aria-label',tr(en,fa));
 render();refreshSafety();
}
menu.addEventListener('click',()=>drawer.hidden?show():dismiss());close.addEventListener('click',dismiss);shade.addEventListener('click',dismiss);
home.addEventListener('click',()=>go('conversation-card'));newChat.addEventListener('click',start);
all.addEventListener('click',()=>{dismiss();focus.openTools()});find.addEventListener('input',render);
archiveToggle.addEventListener('change',render);
document.addEventListener('nexus-studio-state',()=>{refreshSafety();if(!drawer.hidden)render()});
document.addEventListener('nexus-studio-private-clear',()=>{
 find.value='';archiveToggle.checked=false;history.replaceChildren();dismiss();
});
document.addEventListener('input',refreshSafety);
document.addEventListener('change',refreshSafety);
document.addEventListener('nexus-studio-media-state',refreshSafety);
$('language').addEventListener('change',()=>queueMicrotask(labels));
document.addEventListener('keydown',event=>{
 if(event.key==='Escape'&&!drawer.hidden){event.preventDefault();dismiss()}
 if(drawer.hidden||event.key!=='Tab')return;
 const a=[...drawer.querySelectorAll('button,input')].filter(x=>!x.disabled);
 if(event.shiftKey&&document.activeElement===a[0]){event.preventDefault();a.at(-1).focus()}
 else if(!event.shiftKey&&document.activeElement===a.at(-1)){event.preventDefault();a[0].focus()}
});
const more=make('nexus-zen-more','···');$('conversation-card').querySelector('.row').append(more);
more.setAttribute('aria-expanded','false');
function setChatOptions(open){
 document.documentElement.classList.toggle('nexus-chat-options-open',open);
 more.setAttribute('aria-expanded',String(open));more.textContent=open?'×':'···';
}
more.addEventListener('click',()=>setChatOptions(more.getAttribute('aria-expanded')!=='true'));
document.addEventListener('nexus-studio-show-chat-options',()=>setChatOptions(true));
labels();
})();
