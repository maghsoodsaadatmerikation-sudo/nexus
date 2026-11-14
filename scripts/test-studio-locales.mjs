import assert from 'node:assert/strict';
import '../web/studio-locales.js';
const {Registry,MAX_BYTES,MAX_PACKS}=globalThis.NexusLocales,registry=new Registry(),defaults={conversation:'Conversation',save:'Save'};let checks=0;
const value=(code,label=code,dir='ltr')=>({schema:'nexus.studio.locale.v1',code,dir,messages:{conversation:label,save:'Save '+code}});
const install=v=>registry.install(JSON.stringify(v),defaults);
const rejected=v=>{assert.throws(()=>install(v));checks++};
assert.equal(registry.get('es'),null);checks++;
const es=install(value('es','Conversación'));install(value('he','שיחה','rtl'));
assert.equal(registry.get('es'),es);assert.equal(registry.get('he').dir,'rtl');checks++;
assert.throws(()=>es.messages.conversation='mutated');assert.equal(es.messages.conversation,'Conversación');checks++;
install(value('iw','Updated Hebrew','rtl'));assert.equal(registry.get('he').messages.conversation,'Updated Hebrew');assert.equal(registry.get('iw'),null);checks++;
for(const v of [null,[],{},value('en'),value('FA'),value(['es']),value('not_a_language'),{...value('fr'),dir:'auto'},{...value('fr'),messages:null},{...value('fr'),messages:[]},{...value('fr'),messages:{conversation:'only'}},{...value('fr'),messages:{...defaults,extra:'extra'}},{...value('fr'),messages:{...defaults,save:3}},{...value('fr'),messages:{...defaults,save:'  '}},{...value('fr'),messages:{...defaults,save:'x'.repeat(1501)}}])rejected(v);
for(const raw of ['{broken','x'.repeat(MAX_BYTES+1),JSON.stringify({...value('fr'),ignored:'界'.repeat(22000)})]){assert.throws(()=>registry.install(raw,defaults));checks++}
assert.equal(registry.get('es'),es);assert.equal(registry.get('fr'),null);checks++;
for(const code of ['fr','de','it','pt','nl','ja'])install(value(code));
assert.equal(MAX_PACKS,8);assert.throws(()=>install(value('sv')));assert.equal(registry.get('sv'),null);checks++;
const updated=install(value('es','New Spanish'));assert.equal(registry.get('es'),updated);assert.equal(registry.get('he').dir,'rtl');checks++;
assert.equal(registry.get('de').messages.conversation,'de');checks++;
console.log(JSON.stringify({status:'PASS',checks,scope:'bounded-tab-local-label-packs',real_browser_tested:false}));
