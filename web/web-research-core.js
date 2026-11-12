  // Pilot 19: explicit external-web handoff; no application search fetching.
  // Offline shell, signed worker, CSP connect-src 'none', and human authority remain unchanged.
  const NEXUS_SEARCH_PROVIDERS=Object.freeze([
    ['google','Google','https://www.google.com/search?q={searchTerms}'],
    ['bing','Bing','https://www.bing.com/search?q={searchTerms}'],
    ['duckduckgo','DuckDuckGo','https://duckduckgo.com/?q={searchTerms}'],
    ['brave','Brave Search','https://search.brave.com/search?q={searchTerms}'],
    ['ecosia','Ecosia','https://www.ecosia.org/search?q={searchTerms}'],
    ['startpage','Startpage','https://www.startpage.com/sp/search?q={searchTerms}'],
    ['qwant','Qwant','https://www.qwant.com/?q={searchTerms}'],
    ['mojeek','Mojeek','https://www.mojeek.com/search?q={searchTerms}'],
    ['yahoo','Yahoo','https://search.yahoo.com/search?p={searchTerms}'],
    ['yandex','Yandex','https://yandex.com/search/?text={searchTerms}'],
    ['swisscows','Swisscows','https://swisscows.com/en/web?query={searchTerms}'],
    ['baidu','Baidu','https://www.baidu.com/s?wd={searchTerms}'],
    ['scholar','Google Scholar','https://scholar.google.com/scholar?q={searchTerms}'],
    ['pubmed','PubMed','https://pubmed.ncbi.nlm.nih.gov/?term={searchTerms}'],
    ['wikipedia','Wikipedia','https://en.wikipedia.org/w/index.php?search={searchTerms}']
  ]);
  const WEB_RESEARCH_MARKER='NEXUS_SEARCH_QUERY_PLACEHOLDER_1';
  const webSearchStatus=key=>{$('web-search-state').textContent=t(key);};
  const researchStatus=key=>{$('web-source-state').textContent=t(key);};
  function validateExternalHttps(raw,maxLength=2048){
    if(typeof raw!=='string'||!raw.trim()||raw.length>maxLength||/[\x00-\x20\x7f]/.test(raw))
      throw Error('url-value');
    const value=raw.trim();
    if(!/^https:\/\//i.test(value))throw Error('https-only');
    const url=new URL(value);
    const hostname=url.hostname.toLowerCase();
    if(url.protocol!=='https:'||url.username||url.password||url.port||url.hash||
       !hostname.includes('.')||hostname.endsWith('.local')||
       hostname.endsWith('.internal')||hostname.endsWith('.localhost')||
       hostname==='localhost'||hostname==='0.0.0.0'||
       /^\d+(?:\.\d+){3}$/.test(hostname)||hostname.startsWith('[')||
       hostname.includes('%')||!(/^[a-z0-9.-]+$/.test(hostname))||
       hostname.split('.').some(x=>!x||x.startsWith('-')||x.endsWith('-')))
      throw Error('public-https-only');
    return url;
  }
  function validateSearchTemplate(raw){
    if(typeof raw!=='string'||raw.length>450||
       raw.split('{searchTerms}').length!==2)throw Error('template-marker');
    const prepared=raw.replace('{searchTerms}',WEB_RESEARCH_MARKER);
    const url=validateExternalHttps(prepared,450);
    const matches=Array.from(url.searchParams.entries()).filter(([,v])=>v===WEB_RESEARCH_MARKER);
    if(matches.length!==1||url.pathname.includes(WEB_RESEARCH_MARKER)||
       url.hostname.includes(WEB_RESEARCH_MARKER)||
       Array.from(url.searchParams.values()).some(v=>v!==WEB_RESEARCH_MARKER&&v.includes(WEB_RESEARCH_MARKER)))
      throw Error('template-query-param');
    return {url,key:matches[0][0]};
  }
  function cleanManualQuery(value){
    if(typeof value!=='string'||Array.from(value).length>250||
       /[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/.test(value))throw Error('query-bounds');
    const query=value.trim().replace(/\s+/g,' ');
    if(!query)return null;
    return query;
  }
  function prepareSearchUrl(provider,query){
    const q=cleanManualQuery(query);
    if(!q)throw Error('empty-query');
    let template;
    if(provider==='custom')template=$('web-search-custom').value;
    else template=NEXUS_SEARCH_PROVIDERS.find(p=>p[0]===provider)?.[2];
    if(!template)throw Error('unknown-provider');
    const {url,key}=validateSearchTemplate(template);
    url.searchParams.set(key,q);
    if(url.href.length>2600)throw Error('url-bounds');
    return url;
  }
  function showResearchLink(url){
    const slot=$('web-search-link');slot.replaceChildren();
    const a=document.createElement('a');
    a.href=url.href;a.target='_blank';a.rel='noopener noreferrer';
    a.textContent=t('m418')+' '+url.hostname;
    slot.append(a);
  }
  function openExternalResearch(url){
    const a=document.createElement('a');
    a.href=url.href;a.target='_blank';a.rel='noopener noreferrer';
    a.referrerPolicy='no-referrer';
    document.body.append(a);a.click();a.remove();
    showResearchLink(url);
  }
  const webEngine=$('web-search-engine');
  for(const [id,label] of NEXUS_SEARCH_PROVIDERS){
    const option=document.createElement('option');option.value=id;option.textContent=label;webEngine.append(option);
  }
  const custom=document.createElement('option');custom.value='custom';
  custom.textContent=t('m403');webEngine.append(custom);
  function toggleCustomEngine(){
    $('web-search-custom-wrap').hidden=webEngine.value!=='custom';
  }
  webEngine.addEventListener('change',toggleCustomEngine);
  toggleCustomEngine();
  $('web-search-go').addEventListener('click',()=>{
    try{
      const url=prepareSearchUrl(webEngine.value,$('web-search-query').value);
      if(!window.confirm(t('m410')+' '+url.hostname+'?')){webSearchStatus('m411');return;}
      openExternalResearch(url);webSearchStatus('m412');
    }catch{webSearchStatus('m413');$('web-search-link').replaceChildren();}
  });
  $('web-open-url').addEventListener('click',()=>{
    try{
      const url=validateExternalHttps($('web-direct-url').value);
      if(!window.confirm(t('m414')+' '+url.hostname+'?')){webSearchStatus('m411');return;}
      openExternalResearch(url);webSearchStatus('m412');
    }catch{webSearchStatus('m415');$('web-search-link').replaceChildren();}
  });
  $('web-source-draft').addEventListener('click',()=>{
    try{
      const url=validateExternalHttps($('web-source-url').value);
      const excerpt=$('web-source-excerpt').value.trim();
      if(!excerpt||excerpt.length>2000)throw Error('excerpt');
      const source=url.href;
      if(source.length>600)throw Error('source-length');
      if(($('claim').value.trim()||$('source').value.trim())&&
         !window.confirm(t('m344')))return;
      $('claim').value=excerpt;$('source').value=source;
      $('origin').value='external_evidence';$('uncertainty').value='unknown';
      for(const id of ['claim','source'])$(id).dispatchEvent(new Event('input',{bubbles:true}));
      $('claim').focus();researchStatus('m421');
    }catch{researchStatus('m422');}
  });
  $('web-research-clear').addEventListener('click',()=>{
    for(const id of ['web-search-query','web-search-custom','web-direct-url',
      'web-source-url','web-source-excerpt'])$(id).value='';
    $('web-search-link').replaceChildren();
    webSearchStatus('m409');researchStatus('m423');
  });
