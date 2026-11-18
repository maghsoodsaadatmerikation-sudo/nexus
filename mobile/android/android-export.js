/* NEXUS Android export adapter: signed APK-local page only.
 * Android SAF asks user for each output path. No silent shared storage writes.
 * The buffer is sliced in 48 KiB chunks; no whole-film Base64 conversion.
 */
(()=>{
'use strict';
if (!window.NexusExport || window.__NEXUS_NATIVE_EXPORT_INSTALLED__) return;
window.__NEXUS_NATIVE_EXPORT_INSTALLED__=true;
const originals=new Map();
const create=URL.createObjectURL.bind(URL);
const revoke=URL.revokeObjectURL.bind(URL);
URL.createObjectURL=function(blob){
 const id=create(blob);
 if(blob instanceof Blob && originals.size<128) originals.set(id,blob);
 return id;
};
URL.revokeObjectURL=function(id){originals.delete(id);return revoke(id)};
const oldClick=HTMLAnchorElement.prototype.click;
function status(message){
 const element=document.getElementById('motion-status')||
               document.getElementById('status');
 if(element)element.textContent=message;
}
async function exportBlob(blob,name){
 const size=blob.size;
 const filename=String(name||'nexus-export.bin')
   .replace(/[^a-zA-Z0-9_. -]/g,'_').replace(/\.{2,}/g,'_').slice(0,90);
 const type=(blob.type||'application/octet-stream').split(';')[0].toLowerCase();
 if(!Number.isInteger(size)||size<1||size>96*1024*1024)
   throw Error('Android export size must be between 1 byte and 96 MiB');
 const token=window.NexusExport.begin(filename,type,size);
 if(!token)throw Error('Android save is unavailable or another save is in progress');
 try {
  for(let offset=0;offset<size;offset+=48*1024){
   const buffer=new Uint8Array(await blob.slice(offset,offset+48*1024).arrayBuffer());
   let binary='';
   for(let i=0;i<buffer.length;i++)binary+=String.fromCharCode(buffer[i]);
   if(!window.NexusExport.append(token,btoa(binary)))
     throw Error('Android export chunk failed');
  }
  if(!window.NexusExport.finish(token))
    throw Error('Android export did not pass integrity checks');
  status('Android Save As dialog opened; select a destination to finish the export.');
 }catch(e){window.NexusExport.cancel(token);throw e;}
}
HTMLAnchorElement.prototype.click=function(){
 const id=this.href,blob=originals.get(id);
 if(this.download && blob){
   exportBlob(blob,this.download).catch(e=>status('Android export blocked: '+e.message));
   return;
 }
 return oldClick.call(this);
};
})();
