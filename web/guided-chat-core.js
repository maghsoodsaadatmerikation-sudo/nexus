  // Pilot 20: genuine multi-turn *guided* dialogue, deterministic and transparent.
  // No model, remote peer, background networking, retrieval, or authority transfer.
  const CHAT_LIMIT=40,CHAT_INPUT_LIMIT=1500,CHAT_REPLY_LIMIT=1500;
  const CHAT_STAGES=['clarify','evidence','alternatives','uncertainty','values','reflect'];
  const CHAT_PROMPTS=Object.freeze({
    clarify:'m448',evidence:'m449',alternatives:'m450',
    uncertainty:'m451',values:'m452',reflect:'m453'
  });
  let chatTurns=[],chatWorkspace=state.workspace,chatSequence=0,chatSpeechEpoch=0,chatSpeaking=false;
  const chatStatus=key=>{$('chat-state').textContent=t(key);};
  function stopChatSpeech(){
    chatSpeechEpoch++;
    if(chatSpeaking){chatSpeaking=false;try{window.speechSynthesis?.cancel()}catch{}}
    $('chat-speak-stop').disabled=true;
  }
  function updateChatActions(){
    const last=chatTurns.filter(m=>m.role==='human').at(-1);
    const reply=chatTurns.filter(m=>m.role==='guide').at(-1);
    $('chat-as-question').disabled=!last;
    $('chat-as-evidence').disabled=!last;
    $('chat-export').disabled=!chatTurns.length;
    $('chat-clear').disabled=!chatTurns.length&&!$('chat-input').value;
    $('chat-speak').disabled=!reply;
  }
  function renderChatMessages(){
    const log=$('chat-messages');log.replaceChildren();
    if(!chatTurns.length){
      log.append(part('p',t('m444'),'empty'));
    }else{
      for(const item of chatTurns){
        const wrap=part('div','','chat-entry '+(item.role==='human'?'chat-human':'chat-guide'));
        const label=part('strong',t(item.role==='human'?'m445':'m446'));
        const body=part('p',item.text);
        body.dir='auto';wrap.append(label,body);log.append(wrap);
      }
    }
    updateChatActions();
    log.scrollTop=log.scrollHeight;
  }
  function chatClear(switchWorkspace=false){
    stopChatSpeech();
    chatTurns=[];chatSequence=0;$('chat-input').value='';
    $('chat-use-workspace').checked=false;$('chat-focus').value='auto';
    renderChatMessages();chatStatus(switchWorkspace?'m474':'m468');
    refreshDraftNotice();
  }
  function syncChatWorkspace(){
    if(chatWorkspace===state.workspace)return;
    chatWorkspace=state.workspace;chatClear(true);
  }
  function chatReply(human){
    const focus=$('chat-focus').value;
    const humanCount=chatTurns.filter(x=>x.role==='human').length;
    const stage=CHAT_STAGES.includes(focus)?focus:CHAT_STAGES[Math.min(CHAT_STAGES.length-1,humanCount-1)];
    const excerpt=Array.from(human).slice(0,180).join('')+(Array.from(human).length>180?'…':'');
    const pieces=[t('m447')+'“'+excerpt+'”',t(CHAT_PROMPTS[stage])];
    if($('chat-use-workspace').checked){
      const w=state.workspace;
      if(w.question){
        pieces.push(t('m476')+t('m454')+Array.from(w.question).slice(0,140).join(''));
        pieces.push(t('m455')+w.claims.length+t('m456')+w.alternatives.length+t('m457'));
        if(w.values.length)pieces.push(t('m477')+w.values.slice(0,3).map(x=>Array.from(x).slice(0,50).join('')).join(' · '));
      }else pieces.push(t('m458'));
      pieces.push(t('m478'));
    }
    pieces.push(t('m459'));
    return Array.from(pieces.join('\n\n')).slice(0,CHAT_REPLY_LIMIT).join('');
  }
  function chatAdd(role,message){
    if(chatTurns.length>=2*CHAT_LIMIT)throw Error('chat-cap');
    chatTurns.push({id:++chatSequence,role,text:message});
  }
  $('chat-form').addEventListener('submit',event=>{
    event.preventDefault();
    const input=$('chat-input'),human=input.value.trim();
    if(!human||Array.from(human).length>CHAT_INPUT_LIMIT)return chatStatus('m472');
    if(chatTurns.length>=2*CHAT_LIMIT)return chatStatus('m471');
    const context=state.workspace;
    try{
      chatAdd('human',human);
      const reply=chatReply(human);
      if(context!==state.workspace)throw Error('workspace-race');
      chatAdd('guide',reply);
      input.value='';stopChatSpeech();renderChatMessages();
      chatStatus('m473');refreshDraftNotice();input.focus();
    }catch{chatStatus('m471');}
  });
  $('chat-input').addEventListener('input',()=>{
    updateChatActions();refreshDraftNotice();
  });
  $('chat-as-question').addEventListener('click',()=>{
    const last=chatTurns.filter(m=>m.role==='human').at(-1);
    if(!last)return chatStatus('m479');
    if(($('question').value.trim()||$('goal').value.trim()||
        $('constraints').value.trim()||$('values').value.trim())&&
       !window.confirm(t('m465')))return;
    $('question').value=Array.from(last.text).slice(0,1500).join('');
    $('question').dispatchEvent(new Event('input',{bubbles:true}));
    $('question').focus();chatStatus('m466');
  });
  $('chat-as-evidence').addEventListener('click',()=>{
    const last=chatTurns.filter(m=>m.role==='human').at(-1);
    if(!last)return chatStatus('m479');
    if(($('claim').value.trim()||$('source').value.trim())&&
       !window.confirm(t('m465')))return;
    $('claim').value=Array.from(last.text).slice(0,1500).join('');
    $('source').value='';$('origin').value='human';$('uncertainty').value='unknown';
    for(const id of ['claim','source'])$(id).dispatchEvent(new Event('input',{bubbles:true}));
    $('claim').focus();chatStatus('m467');
  });
  $('chat-export').addEventListener('click',()=>{
    if(!chatTurns.length)return;
    if(!window.confirm(t('m469')))return;
    const text=['NEXUS — Guided Conversation','Human authority: unchanged',
      'Local scripted reflection, not a generative model or verified advice','',
      ...chatTurns.map(x=>(x.role==='human'?t('m445'):t('m446'))+':\n'+x.text+'\n')
    ].join('\n');
    downloadFileBlob(new Blob([text],{type:'text/plain;charset=utf-8'}),
      'nexus-guided-conversation.txt');
    chatStatus('m470');
  });
  $('chat-clear').addEventListener('click',()=>{if(window.confirm(t('m491')))chatClear(false);});
  $('chat-speak').addEventListener('click',()=>{
    stopChatSpeech();
    const reply=chatTurns.filter(m=>m.role==='guide').at(-1);
    if(!reply)return chatStatus('m489');
    try{
      const speech=window.speechSynthesis,Native=window.SpeechSynthesisUtterance;
      const lang=interfaceLang.split('-')[0].toLowerCase();
      const voices=Array.from(speech?.getVoices?.()||[]);
      const local=voices.find(v=>v.localService===true&&
        String(v.lang).split('-')[0].toLowerCase()===lang);
      if(!local||!Native)throw Error('local-voice-not-available');
      // Never use a remote browser TTS provider. Stop existing app voice first.
      stopVoice(false);
      const utterance=new Native(Array.from(reply.text).slice(0,1500).join(''));
      utterance.voice=local;utterance.lang=local.lang;
      const epoch=++chatSpeechEpoch;chatSpeaking=true;
      utterance.onend=()=>{if(epoch===chatSpeechEpoch)stopChatSpeech();};
      utterance.onerror=()=>{if(epoch===chatSpeechEpoch){stopChatSpeech();chatStatus('m485');}};
      $('chat-speak-stop').disabled=false;
      speech.speak(utterance);chatStatus('m486');
    }catch{stopChatSpeech();chatStatus('m485');}
  });
  $('chat-speak-stop').addEventListener('click',()=>{
    stopChatSpeech();chatStatus('m487');
  });
  window.addEventListener('pagehide',stopChatSpeech);
