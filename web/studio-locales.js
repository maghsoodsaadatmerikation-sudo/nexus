/* Tab-local, bounded label packs. No project state or executable content. */
(function(root){'use strict';
const MAX_BYTES=64000,MAX_PACKS=8,fail=()=>{throw Error('language-pack')};
class Registry{
 #packs=new Map();
 get(code){return this.#packs.get(code)||null}
 install(raw,defaults,{optionalKeys=[]}={}){
  if(typeof raw!=='string'||new TextEncoder().encode(raw).length>MAX_BYTES)fail();
  const value=JSON.parse(raw);
  if(!value||value.schema!=='nexus.studio.locale.v1'||typeof value.code!=='string')fail();
  const code=Intl.getCanonicalLocales(value.code)[0];
  if(!code||['en','fa'].includes(code)||!['ltr','rtl'].includes(value.dir)||!value.messages||typeof value.messages!=='object'||Array.isArray(value.messages))fail();
  // New labels can fall back to defaults while earlier packs retain their translations.
  const missing=Object.keys(defaults).filter(key=>!Object.hasOwn(value.messages,key));
  if(missing.some(key=>!optionalKeys.includes(key))||
     Object.entries(value.messages).some(([key,label])=>!Object.hasOwn(defaults,key)||
      typeof label!=='string'||!label.trim()||label.length>1500))fail();
  if(!this.#packs.has(code)&&this.#packs.size>=MAX_PACKS)fail();
  const pack=Object.freeze({code,dir:value.dir,messages:Object.freeze({...defaults,...value.messages})});
  this.#packs.set(code,pack);return pack;
 }
}
root.NexusLocales=Object.freeze({Registry,MAX_BYTES,MAX_PACKS});
})(globalThis);
