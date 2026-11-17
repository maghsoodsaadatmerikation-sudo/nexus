#!/usr/bin/env bash
# Exact source of independently observed public assets; provider deployment commit is not inferred.
# Candidate source is tested separately and NEVER silently treated as published.
set -euo pipefail
baseline=35be3d4b0da0d0f21e04a4a8a61f45e316a0058e
test -n "${RUNNER_TEMP:-}"
target="$RUNNER_TEMP/nexus-live-pilot"
test ! -e "$target"
mkdir -m 700 "$target"
# Public-browser assertions must come from the same immutable revision as
# the HTML they exercise. Copying candidate scripts here would silently mix
# a newer test contract with an older deployed app and produce a false red.
# Candidate checks remain in their separate PR/offline CI workflows.
git archive "$baseline" web public scripts | tar -x -C "$target"
# Use exactly the deployed revision for ALL application bytes. On public HTTPS,
# the cached HTML body can exist before its inline DOM handlers finish parsing.
# The historical Chromium witness only checked existence of the install button,
# which races the DOMContentLoaded listener and could report a false offline
# failure. Pin the historical witness's Git blob and change exactly its
# navigation-readiness predicate; no published asset/source/consent contract
# can be modified by this correction.
expected_witness_blob=b259a38f8005dabef3afbcc6b97e77cdd563594c
actual_witness_blob="$(git hash-object "$target/scripts/test-pwa-offline-browser.mjs")"
test "$actual_witness_blob" = "$expected_witness_blob"
python3 - "$target/scripts/test-pwa-offline-browser.mjs" <<'PY'
from pathlib import Path
import hashlib, json, sys
path=Path(sys.argv[1])
text=path.read_text()
before="""await poll(()=>retryJs("document.getElementById('offline-install') && navigator.onLine===false"),15000,'offline-navigation-not-served');"""
after="""await poll(()=>retryJs("document.readyState==='complete' && document.getElementById('offline-install') && navigator.onLine===false"),15000,'offline-navigation-not-served');"""
if text.count(before)!=1 or after in text:
    raise SystemExit("BLOCKED: pinned real-browser witness predicate changed")
text=text.replace(before,after)
# JS Runtime.evaluate previously threw for the demo, obscuring whether
# the installed public page failed to initialize or a real user action was
# refused. Keep the exact demo click and assertion; catch only to report
# safe technical flags (never page text).
demo_before="""const offline=await js("(()=>{document.getElementById('load-demo').click();return {question:document.getElementById('question-view').textContent,claims:document.getElementById('claims').querySelectorAll('.entry').length,options:document.getElementById('alternatives').querySelectorAll('.entry').length,decision:document.getElementById('decision-view').textContent,net:navigator.onLine}})()");"""
demo_after="""// A single CDP readyState observation can come from a document that
// immediately navigates again. Demand two observations from the same
// actual offline-controlled public document before the one synthetic click.
// Never count a browser error document, missing SW controller, or partial DOM.
const stableReadiness=()=>retryJs("(()=>{const ready=document.readyState==='complete' && !!document.getElementById('load-demo') && !!document.getElementById('question-view') && !!document.getElementById('claims') && !!document.getElementById('alternatives') && !!document.getElementById('decision-view') && navigator.onLine===false && navigator.serviceWorker?.controller?.scriptURL===location.origin+'/service-worker.js' && document.documentElement.outerHTML.includes('nexus.offline-pilot.v1');return ready?{epoch:performance.timeOrigin,href:location.href}:null})()");
let offlineDocumentEpoch=null;
await poll(async()=>{
  const first=await stableReadiness();
  if(!first || first.href!==ORIGIN){offlineDocumentEpoch=null;return false;}
  if(first.epoch!==offlineDocumentEpoch){offlineDocumentEpoch=first.epoch;return false;}
  await delay(300);
  const second=await stableReadiness();
  return !!second && second.href===ORIGIN && second.epoch===offlineDocumentEpoch;
},20000,'offline-cached-app-did-not-reach-stable-ready-state');
const offline=await js("(()=>{try{document.getElementById('load-demo').click();return {question:document.getElementById('question-view').textContent,claims:document.getElementById('claims').querySelectorAll('.entry').length,options:document.getElementById('alternatives').querySelectorAll('.entry').length,decision:document.getElementById('decision-view').textContent,net:navigator.onLine,client_error:'none',language:document.documentElement.lang}}catch(error){return {question:'',claims:0,options:0,decision:'',net:navigator.onLine,client_error:error?.name||'unknown',language:document.documentElement.lang,ready:document.readyState,has_demo:!!document.getElementById('load-demo'),has_question:!!document.getElementById('question-view'),has_claims:!!document.getElementById('claims'),has_options:!!document.getElementById('alternatives'),has_decision:!!document.getElementById('decision-view'),has_installer:!!document.getElementById('offline-install'),has_reviewed_schema:document.documentElement.outerHTML.includes('nexus.offline-pilot.v1'),worker_controls:!!navigator.serviceWorker?.controller}}})()");"""
if text.count(demo_before)!=1 or demo_after in text:
    raise SystemExit("BLOCKED: pinned demo click contract changed")
text=text.replace(demo_before,demo_after)
# Sanitized diagnostics on failure. Never print user content, synthetic page
# text, network tokens or private file content, even on a public CI runner.
before_assert=""" assert(offline.question.includes('ساختگی')&&offline.claims===2&&offline.options===2&&
 offline.decision.includes('هیچ تصمیم انسانی')&&offline.net===false,
 'offline-content-unavailable-or-created-a-judgment');"""
after_assert=""" const offlineContract={fictional_question:offline.question.includes('ساختگی'),
   two_claims:offline.claims===2,two_options:offline.options===2,
   no_human_judgment:offline.decision.includes('هیچ تصمیم انسانی'),
   browser_offline:offline.net===false,
   client_error:offline.client_error, language:offline.language,
   dom_ready:offline.ready,has_demo:offline.has_demo,has_question:offline.has_question,
   has_claims:offline.has_claims,has_options:offline.has_options,
   has_decision:offline.has_decision,has_installer:offline.has_installer,
   has_reviewed_schema:offline.has_reviewed_schema,worker_controls:offline.worker_controls};
 if(Object.values(offlineContract).some((value,i)=>i<5&&!value)||offline.client_error!=='none')
   process.stderr.write(JSON.stringify({event:'pilot12-public-offline-diagnostic',
     ...offlineContract})+'\\n');
 assert(offlineContract.fictional_question&&offlineContract.two_claims&&offlineContract.two_options&&
   offlineContract.no_human_judgment&&offlineContract.browser_offline&&offline.client_error==='none',
 'offline-content-unavailable-or-created-a-judgment');"""
if text.count(before_assert)!=1 or after_assert in text:
    raise SystemExit("BLOCKED: historical offline acceptance shape changed")
text=text.replace(before_assert,after_assert)

# Diagnose an intermittent REAL PUBLIC Chrome offline navigation failure using
# public-safe CDP booleans only; never log request URLs or page/user content.
# The archived page, Service Worker and original eight assertions stay pinned.
trace_decl_before="""const checks=[];"""
trace_decl_after="""const checks=[];
const navTrace={responses:[],failures:[],frames:[]};
const capped=(name,record)=>{const entries=navTrace[name];entries.push(record);if(entries.length>8)entries.shift();};"""
if text.count(trace_decl_before)!=1 or trace_decl_after in text:
    raise SystemExit("BLOCKED: historical CDP trace declaration changed")
text=text.replace(trace_decl_before,trace_decl_after)
trace_listener_before="""  const msg=JSON.parse(e.data),p=pending.get(msg.id);
  if(!p)return;pending.delete(msg.id);"""
trace_listener_after="""  const msg=JSON.parse(e.data),p=pending.get(msg.id);
  if(msg.method==='Network.responseReceived'&&msg.params?.type==='Document'){
    const r=msg.params.response||{};
    capped('responses',{stage,app_origin:r.url===ORIGIN,
      from_service_worker:r.fromServiceWorker===true,status:Number(r.status)||0,
      html:r.mimeType==='text/html'});
  }
  if(msg.method==='Network.loadingFailed'&&msg.params?.type==='Document'){
    const reason=String(msg.params.errorText||'');
    capped('failures',{stage,disconnected:reason.includes('ERR_INTERNET_DISCONNECTED'),
      aborted:reason.includes('ERR_ABORTED'),other:!reason.includes('ERR_INTERNET_DISCONNECTED')&&!reason.includes('ERR_ABORTED')});
  }
  if(msg.method==='Page.frameNavigated'){
    const u=String(msg.params?.frame?.url||'');
    capped('frames',{stage,app_origin:u===ORIGIN,browser_error:u.startsWith('chrome-error:')});
  }
  if(!p)return;pending.delete(msg.id);"""
if text.count(trace_listener_before)!=1 or trace_listener_after in text:
    raise SystemExit("BLOCKED: historical CDP event handler changed")
text=text.replace(trace_listener_before,trace_listener_after)
trace_catch_before="""}catch(error){
 process.stderr.write(JSON.stringify({event:'pwa-browser-fail-closed',stage,"""
trace_catch_after="""}catch(error){
 if(stage==='real-network-offline')
   process.stderr.write(JSON.stringify({event:'pilot12-public-cdp-navigation',
     ...navTrace,contains_page_content:false,authority:'none'})+'\\n');
 process.stderr.write(JSON.stringify({event:'pwa-browser-fail-closed',stage,"""
if text.count(trace_catch_before)!=1 or trace_catch_after in text:
    raise SystemExit("BLOCKED: historical failure handler changed")
text=text.replace(trace_catch_before,trace_catch_after)


# The page-only CDP Network offline flag does not necessarily apply to
# Service Worker network fetches. Attach to the *exact reviewed worker*
# target and independently test an online baseline followed by an offline
# worker-origin fetch rejection before accepting an offline navigation.
# Keep the pinned archived page and worker unchanged.
def replace_once(old, new, label):
    global text
    if text.count(old)!=1 or new in text:
        raise SystemExit("BLOCKED: pinned worker-proof anchor changed: "+label)
    text=text.replace(old,new)

replace_once("const rpc=(method,params={},deadline=10000)=>new Promise(",
             "const rpc=(method,params={},deadline=10000,sessionId=null)=>new Promise(",
             "session-aware-rpc-signature")
replace_once("socket.send(JSON.stringify({id,method,params}));",
             "socket.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}));",
             "session-aware-rpc-transport")
replace_once("const navTrace={responses:[],failures:[],frames:[]};",
             "const navTrace={responses:[],failures:[],frames:[]};\n"
             "const workerProof={exact_target:false,online_probe:false,offline_probe:false,document_from_worker:false};",
             "worker-proof-evidence")

attach_anchor=""" checks.push('installed-cache-sha256-is-exact-reviewed-html');"""
attach_code=""" // Require the exact same-origin installed service worker TARGET, not
 // merely the page's navigator.onLine or ServiceWorker.controller flag.
 stage='worker-target-online-proof';
 await rpc('Target.setDiscoverTargets',{discover:true});
 const workerInfo=await poll(async()=>{
   const list=await rpc('Target.getTargets');
   const matching=(list.targetInfos||[]).filter(x=>
     x.type==='service_worker'&&x.url===ORIGIN+'service-worker.js');
   return matching.length===1?matching[0]:null;
 },16000,'exact-public-service-worker-target-missing');
 const attached=await rpc('Target.attachToTarget',
   {targetId:workerInfo.targetId,flatten:true});
 assert(typeof attached.sessionId==='string'&&attached.sessionId.length>4,
   'worker-target-attach-refused');
 const workerSessionId=attached.sessionId;
 await rpc('Runtime.enable',{},10000,workerSessionId);
 await rpc('Network.enable',{},10000,workerSessionId);
 await rpc('Network.setCacheDisabled',{cacheDisabled:true},10000,workerSessionId);
 workerProof.exact_target=true;
 const onlineProbe=await rpc('Runtime.evaluate',{
   expression:"fetch('/',{cache:'no-store',credentials:'omit'}).then(r=>r.status===200,()=>false)",
   awaitPromise:true,returnByValue:true},15000,workerSessionId);
 assert(onlineProbe.result?.value===true&&!onlineProbe.exceptionDetails,
   'worker-origin-baseline-not-online');
 workerProof.online_probe=true;
 checks.push('installed-cache-sha256-is-exact-reviewed-html');"""
replace_once(attach_anchor,attach_code,"public-worker-attach")

offline_anchor=""" await rpc('Network.emulateNetworkConditions',{offline:true,latency:0,downloadThroughput:0,uploadThroughput:0});
 await rpc('Page.reload',{ignoreCache:true});"""
offline_code=""" const offlineParams={offline:true,latency:0,downloadThroughput:0,uploadThroughput:0};
 // Both independent CDP targets are explicitly disconnected. A page-only
 // offline signal does not meet the acceptance contract.
 await rpc('Network.emulateNetworkConditions',offlineParams);
 await rpc('Network.emulateNetworkConditions',offlineParams,10000,workerSessionId);
 const workerBlocked=await rpc('Runtime.evaluate',{
   expression:"fetch('/',{cache:'no-store',credentials:'omit'}).then(()=>false,()=>true)",
   awaitPromise:true,returnByValue:true},15000,workerSessionId);
 assert(workerBlocked.result?.value===true&&!workerBlocked.exceptionDetails,
   'worker-origin-network-still-reachable');
 workerProof.offline_probe=true;
 await rpc('Page.reload',{ignoreCache:true});"""
replace_once(offline_anchor,offline_code,"both-cdp-targets-offline")

doc_anchor=""" checks.push('real-chrome-network-offline-reload-served-cached-app');"""
doc_code=""" // Chromium can omit Network.responseReceived for a SW CacheStorage
 // navigation while still exposing Resource Timing's workerStart. Require
 // the browser's *real navigation* workerStart and an exact controller;
 // if a CDP Document event exists, it must be an approved worker HTML 200.
 const navigation=await retryJs("(()=>{const n=performance.getEntriesByType('navigation')[0];return {worker_started:Number(n?.workerStart)>0,controlled:navigator.serviceWorker?.controller?.scriptURL===location.origin+'/service-worker.js',status:Number(n?.responseStatus)||0}})()");
 assert(navigation?.worker_started===true&&navigation?.controlled===true,
   'offline-navigation-worker-timing-not-confirmed');
 const offlineDocuments=navTrace.responses.filter(r=>
   r.stage==='real-network-offline'&&r.app_origin);
 assert(offlineDocuments.every(r=>r.from_service_worker&&r.status===200&&r.html),
   'offline-navigation-cdp-document-contradicts-worker-timing');
 workerProof.document_from_worker=true;
 checks.push('real-chrome-network-offline-reload-served-cached-app');
 checks.push('worker-target-network-baseline-then-offline-rejection');"""
replace_once(doc_anchor,doc_code,"offline-document-worker-origin")

report_anchor="""   actual_offline_navigation:true,real_android_hardware:false,"""
report_code="""   actual_offline_navigation:true,
   worker_target_network_isolated:workerProof.exact_target&&workerProof.online_probe&&
     workerProof.offline_probe&&workerProof.document_from_worker,
   worker_online_baseline:true,real_android_hardware:false,"""
replace_once(report_anchor,report_code,"worker-proof-report")


path.write_text(text)
print(json.dumps({'witness_source':'pinned-deployed-baseline',
  'witness_patch':'pinned-worker-target-online-offline-network-proof',
  'witness_sha256':hashlib.sha256(text.encode()).hexdigest(),
  'published_application_bytes_modified':False,
  'acceptance_checks_relaxed':False, 'authority':'none'},sort_keys=True), file=sys.stderr)
PY
python3 - "$baseline" "$target" <<'PY'
import hashlib,json,sys
from pathlib import Path
source=Path('web/offline-pilot.html').read_bytes()
live=(Path(sys.argv[2])/'web/offline-pilot.html').read_bytes()
print(json.dumps({'asset_source_commit':sys.argv[1],'provider_deployment_commit_verified':False,
 'expected_published_html_sha256':hashlib.sha256(live).hexdigest(),
 'candidate_html_sha256':hashlib.sha256(source).hexdigest(),
 'candidate_equals_published_source':source==live,
 'candidate_promoted_by_this_step':False,'authority':'none'}))
PY
