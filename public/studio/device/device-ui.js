import {DeviceEngine} from './device-engine.js';
const $=id=>document.getElementById(id),text=(en,fa)=>document.documentElement.lang==='fa'?fa:en;
const engine=new DeviceEngine({workerURL:new URL('./device-worker.js',import.meta.url),onStatus:data=>{
 if(data.type==='phase')$('device-state').textContent=text('Loading local runtime: ','بارگذاری موتور محلی: ')+data.stage;
 else if(data.type==='download')$('device-state').textContent=text('Downloading public model file: ','دانلود فایل عمومی مدل: ')+data.file+' · '+Math.round(data.loaded/1048576)+' / '+Math.ceil(data.total/1048576)+' MiB';
 else if(data.type==='ready')$('device-state').textContent=text('Small model ready on this device. English drafts; limited accuracy.','مدل کوچک روی دستگاه آماده است؛ پیش‌نویس انگلیسی با دقت محدود.');
 else if(data.type==='generating')$('device-state').textContent=text('Generating locally. Stop terminates the Worker.','تولید روی دستگاه؛ توقف، پردازش مدل را قطع می‌کند.');
 else if(data.type==='error')$('device-state').textContent=data.code==='context-too-large'?text('Context exceeds the small model limit. Shorten it manually, then prepare again.','ورودی از ظرفیت مدل کوچک بیشتر است؛ آن را دستی کوتاه کن و دوباره آماده کن.'):text('Local generation failed. Try again or unload the model.','تولید محلی انجام نشد؛ دوباره تلاش کن یا مدل را از حافظه خارج کن.');
 else if(data.type==='idle')$('device-state').textContent=text('Model is unloaded. Conversations were retained.','مدل از حافظه خارج است؛ گفت‌وگوها حفظ شدند.');
 $('device-load').disabled=engine.state!=='idle';
}});
window.NexusDevice=engine;
let previous={mode:$('model-mode').value,budget:$('model-budget').value};
$('model-engine').onchange=()=>{
 window.NexusStudioUI.resetModel();const local=$('model-engine').value==='device';
 if(local){previous={mode:$('model-mode').value,budget:$('model-budget').value};$('model-mode').value='standard';$('model-budget').value='64';$('model-budget').max='64'}
 else{$('model-mode').value=previous.mode;$('model-budget').value=previous.budget;$('model-budget').max='8192'}
 $('model-mode').disabled=local;
};
$('device-load').onclick=async()=>{
 if(!$('device-consent').checked){$('device-state').textContent=text('Choose the download consent first.','ابتدا اجازهٔ دانلود را انتخاب کن.');return}
 window.NexusStudioUI.resetModel();$('device-load').disabled=true;$('device-state').textContent=text('Loading verified public model files…','بارگذاری فایل‌های عمومیِ بررسی‌شدهٔ مدل…');
 try{await engine.load({consent:true})}catch(error){$('device-state').textContent=text('Model unavailable: ','مدل در دسترس نیست: ')+error.message+' · '+text('Check network, storage and device memory.','اتصال، فضای ذخیره‌سازی و حافظهٔ دستگاه را بررسی کن.')}finally{$('device-load').disabled=engine.state!=='idle'}
};
$('device-consent').onchange=()=>{if(!$('device-consent').checked){engine.unload();window.NexusStudioUI.resetModel()}};
$('device-unload').onclick=()=>{engine.unload();window.NexusStudioUI.resetModel()};
$('device-erase').onclick=async()=>{try{await engine.erase();window.NexusStudioUI.resetModel();$('device-state').textContent=text('Downloaded model/runtime cache removed. Conversations and encrypted archives were retained.','کش مدل و موتور اجرا حذف شد؛ گفت‌وگوها و آرشیوهای رمزگذاری‌شده حفظ شدند.')}catch{$('device-state').textContent=text('Model cache could not be removed.','کش مدل حذف نشد.')}};
