/* Tab-local, bounded label packs. No project state or executable content. */
(function(root){'use strict';
const MAX_BYTES=64000,MAX_PACKS=8,fail=()=>{throw Error('language-pack')};
class Registry{
 #packs=new Map();
 get(code){return this.#packs.get(code)||null}
 install(raw,defaults){
  if(typeof raw!=='string'||new TextEncoder().encode(raw).length>MAX_BYTES)fail();
  const value=JSON.parse(raw);
  if(!value||value.schema!=='nexus.studio.locale.v1'||typeof value.code!=='string')fail();
  const code=Intl.getCanonicalLocales(value.code)[0];
  if(!code||['en','fa'].includes(code)||!['ltr','rtl'].includes(value.dir)||!value.messages||typeof value.messages!=='object'||Array.isArray(value.messages))fail();
  if(Object.keys(value.messages).sort().join('|')!==Object.keys(defaults).sort().join('|')||Object.values(value.messages).some(s=>typeof s!=='string'||!s.trim()||s.length>1500))fail();
  if(!this.#packs.has(code)&&this.#packs.size>=MAX_PACKS)fail();
  const pack=Object.freeze({code,dir:value.dir,messages:Object.freeze({...value.messages})});
  this.#packs.set(code,pack);return pack;
 }
}
root.NexusLocales=Object.freeze({Registry,MAX_BYTES,MAX_PACKS});
})(globalThis);
