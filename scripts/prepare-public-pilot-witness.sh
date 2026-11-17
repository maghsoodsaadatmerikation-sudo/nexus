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
# The only candidate addition is a test-only browser egress proxy; it cannot
# replace any pinned public application/source/worker/browser logic.
test "$(git hash-object scripts/pilot12-public-egress-proxy.mjs)" = "$(git rev-parse HEAD:scripts/pilot12-public-egress-proxy.mjs)"
cp scripts/pilot12-public-egress-proxy.mjs "$target/scripts/pilot12-public-egress-proxy.mjs"
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


# Browser-wide public HTTPS egress isolation: Chrome's CONNECT proxy is
# allowlisted to the single reviewed public origin. Cut its actual tunnels
# after opt-in registration so BOTH page and Service Worker lose network.
# Network.overrideNetworkState only changes page onLine display; evidence
# relies on physical proxy refusal, not its boolean alone.
def replace_exact(old,new,label):
    global text
    if text.count(old)!=1 or new in text:
        raise SystemExit('BLOCKED: pinned proxy witness anchor: '+label)
    text=text.replace(old,new)

# The page onLine flag is NOT evidence of a whole-browser outage. The actual
# Chrome CONNECT egress cut below provides independent network disconnection.
replace_exact("document.readyState==='complete' && document.getElementById('offline-install') && navigator.onLine===false",
    "document.readyState==='complete' && document.getElementById('offline-install')",
    "offline-navigation-no-boolean-shortcut")
replace_exact("&& navigator.onLine===false && navigator.serviceWorker?.controller?.scriptURL",
    "&& navigator.serviceWorker?.controller?.scriptURL",
    "stable-nav-does-not-require-page-network-emulation")
replace_exact("browser_offline:offline.net===false",
    "origin_proxy_cut:proxy.stats().live===false&&proxy.stats().active===0",
    "offline-acceptance-uses-actual-proxy")
replace_exact("offlineContract.browser_offline",
    "offlineContract.origin_proxy_cut",
    "synthetic-demo-contract-uses-actual-proxy")

replace_exact("import path from 'node:path';",
    "import path from 'node:path';\nimport {startProbeProxy} from './pilot12-public-egress-proxy.mjs';",
    "proxy-module-import")
replace_exact("const profile=await mkdtemp(path.join(tmpdir(),'nexus-pwa-private-'));",
    "const profile=await mkdtemp(path.join(tmpdir(),'nexus-pwa-private-'));\nconst proxy=await startProbeProxy();",
    "ephemeral-proxy-launch")
replace_exact(" '--user-data-dir='+profile,'--window-size=500,980','about:blank'",
    " '--proxy-server=http://127.0.0.1:'+proxy.port,\n '--user-data-dir='+profile,'--window-size=500,980','about:blank'",
    "chrome-bounded-proxy")
replace_exact(" await rpc('Network.emulateNetworkConditions',{offline:true,latency:0,downloadThroughput:0,uploadThroughput:0});",
    """ const beforeCut=proxy.stats();
 assert(beforeCut.allowed>0,
   'public-browser-did-not-actually-use-allowlisted-proxy');
 await proxy.cut();
 assert(proxy.stats().live===false&&proxy.stats().active===0,
   'browser-origin-tunnels-still-open');
 // No CDP page-offline setting: it can bypass or abort SW navigation.
 // Actual browser HTTPS egress is blocked by the physical CONNECT proxy cut.
 // navigator.onLine may still be true; this is NOT the acceptance condition.""",
    "force-network-cut-before-reload")
replace_exact(" checks.push('real-chrome-network-offline-reload-served-cached-app');",
    """ const navProof=await retryJs("(()=>{const n=performance.getEntriesByType('navigation')[0];return {worker_started:Number(n?.workerStart)>0,controller:navigator.serviceWorker?.controller?.scriptURL===location.origin+'/service-worker.js'}})()");
 assert(navProof?.worker_started===true&&navProof.controller===true,
   'public-offline-navigation-not-proved-worker-delivered');
 assert(proxy.stats().live===false&&proxy.stats().active===0,
   'public-egress-regained-unexpectedly');
 const observed=navTrace.responses.filter(r=>r.stage==='real-network-offline'&&r.app_origin);
 assert(observed.every(r=>r.from_service_worker&&r.status===200&&r.html),
   'public-offline-network-observation-not-from-worker');
 checks.push('real-chrome-network-offline-reload-served-cached-app');
 checks.push('chrome-proxy-cut-with-worker-served-cache');""",
    "worker-delivery-after-full-proxy-cut")
replace_exact("   actual_offline_navigation:true,real_android_hardware:false,",
    """   actual_offline_navigation:true,
   chromium_origin_proxy_cut:proxy.stats().live===false&&
     proxy.stats().active===0&&proxy.stats().allowed>0,
   isolated_to_reviewed_public_origin:true,real_android_hardware:false,""",
    "proxy-disconnection-report")
replace_exact(" if(stage==='real-network-offline')\n   process.stderr.write(JSON.stringify({event:'pilot12-public-cdp-navigation',",
    " if(['online-bootstrap','real-network-offline'].includes(stage))\n   process.stderr.write(JSON.stringify({event:'pilot12-proxy-diagnostic',...proxy.stats(),authority:'none'})+'\\n');\n if(stage==='real-network-offline')\n   process.stderr.write(JSON.stringify({event:'pilot12-public-cdp-navigation',",
    "proxy-failure-counter")
replace_exact(" await rm(profile,{recursive:true,force:true});",
    " await proxy.close();\n await rm(profile,{recursive:true,force:true});",
    "close-disposable-proxy")

path.write_text(text)
print(json.dumps({'witness_source':'pinned-deployed-baseline',
  'witness_patch':'pinned-public-browser-proxy-egress-cut-and-worker-navigation',
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
