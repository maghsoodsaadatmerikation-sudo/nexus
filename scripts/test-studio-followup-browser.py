#!/usr/bin/env python3
"""Continuation retrieval in the generated Studio runtime, using synthetic data.

Exercises the context API in real Chromium; not a composer UI or live model test.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('studio_browser', ROOT/'scripts/test-studio-browser.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.MIN_CHECKS = 160
module.WITNESS = r"""
window.addEventListener('load',()=>{
 const S=NexusStudio,checks=[],assert=(value,label)=>{if(!value)throw Error(label);checks.push(label)};
 try{
  const p=S.project('Synthetic continuation project');
  p.sources=[{id:S.uid(),name:'orchard.txt',text:'orchard SOURCE_MARKER'},
   {id:S.uid(),name:'violet.txt',text:'violet NEW_TOPIC_MARKER'}];
  const prior=S.append(S.thread('Earlier orchard'),'user','orchard PRIOR_MARKER','human');
  const other=S.append(S.thread('Earlier violet'),'user','violet PRIOR_NEW_TOPIC','human');
  let t=S.append(S.thread('Active'),'user','orchard','human');
  const hidden=S.append(t,'user','violet HIDDEN_BRANCH','human',null);
  t={...t,nodes:hidden.nodes};
  t=S.append(t,'assistant','violet MODEL_ONLY','model');
  p.threads=[prior,other,t];
  const before=JSON.stringify(p);
  const commands=['continue','GO ON!','keep going','next step','ادامه بده','ادامه','ادامه دهید','گام بعدی؟','قدم بعدی'];
  for(const command of commands){
   const next=S.append(t,'user',command,'human');
   for(const sources of [false,true])for(const relatedChats of [false,true]){
    const label=command+'/'+sources+'/'+relatedChats;
    const ctx=S.context(p,next,{sources,relatedChats,skyTone:false});
    assert(ctx.messages.at(-1).content===command,label+'/original-message');
    assert(ctx.citations.length===(sources?1:0),label+'/source-consent');
    assert(ctx.recalled_chats.length===(relatedChats?1:0),label+'/chat-consent');
    assert(ctx.continuation_retrieval===(sources||relatedChats),label+'/review-flag');
    assert(!sources||ctx.citations[0].name==='orchard.txt',label+'/active-topic-source');
    assert(!relatedChats||ctx.recalled_chats[0].thread===prior.id,label+'/active-topic-chat');
    assert(!ctx.messages[0].content.includes('HIDDEN_BRANCH')&&!ctx.messages[0].content.includes('MODEL_ONLY'),label+'/no-hidden-or-model-topic');
   }
  }
  const options={sources:true,relatedChats:true,skyTone:false};
  let changed=S.append(t,'user','violet','human');
  changed=S.append(S.append(changed,'assistant','orchard MODEL_ONLY','model'),'user','continue','human');
  const current=S.context(p,changed,options);
  assert(current.citations[0].name==='violet.txt','latest-substantive-user-topic-wins');
  assert(current.recalled_chats[0].thread===other.id,'chat-recall-uses-new-topic');
  const explicit=S.context(p,S.append(t,'user','continue with violet','human'),options);
  assert(explicit.citations[0].name==='violet.txt','explicit-request-keeps-own-query');
  assert(!explicit.messages[0].content.includes('Search topic carried'),'explicit-request-not-marked-carried');
  assert(explicit.continuation_retrieval===false,'new-topic-omits-review-flag');
  let long=S.append(S.thread('Truncated'),'user','orchard','human');
  for(let i=0;i<22;i++)long=S.append(S.append(long,'assistant','draft','model'),'user','continue','human');
  const dropped=S.context(p,long,options);
  assert(dropped.omitted_messages>0&&!dropped.citations.length&&!dropped.recalled_chats.length&&
   !dropped.continuation_retrieval,'omitted-topic-stays-omitted');
  const empty=S.context(p,S.append(S.thread('Fresh'),'user','continue','human'),options);
  assert(!empty.citations.length&&!empty.recalled_chats.length,'fresh-continuation-has-no-invented-topic');
  const isolated=S.context(p,{...changed,isolated:true,temporary:true},options);
  assert(!isolated.citations.length&&!isolated.recalled_chats.length,'isolated-chat-has-no-project-retrieval');
  assert(JSON.stringify(p)===before,'context-preparation-does-not-mutate-project');
  document.getElementById('nexus-browser-result').textContent=JSON.stringify({status:'PASS',checks,real_model_tested:false,scope:'generated-runtime-context-api',authority:'none'});
 }catch(error){document.getElementById('nexus-browser-result').textContent=JSON.stringify({status:'FAIL',reason:error.message,checks})}
});
"""

if __name__ == '__main__':
    module.main()
