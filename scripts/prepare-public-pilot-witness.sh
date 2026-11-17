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
demo_after="""const offline=await js("(()=>{try{document.getElementById('load-demo').click();return {question:document.getElementById('question-view').textContent,claims:document.getElementById('claims').querySelectorAll('.entry').length,options:document.getElementById('alternatives').querySelectorAll('.entry').length,decision:document.getElementById('decision-view').textContent,net:navigator.onLine,client_error:'none',language:document.documentElement.lang}}catch(error){return {question:'',claims:0,options:0,decision:'',net:navigator.onLine,client_error:error?.name||'unknown',language:document.documentElement.lang}}})()");"""
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
   client_error:offline.client_error, language:offline.language};
 if(Object.values(offlineContract).some((value,i)=>i<5&&!value)||offline.client_error!=='none')
   process.stderr.write(JSON.stringify({event:'pilot12-public-offline-diagnostic',
     ...offlineContract})+'\\n');
 assert(offlineContract.fictional_question&&offlineContract.two_claims&&offlineContract.two_options&&
   offlineContract.no_human_judgment&&offlineContract.browser_offline&&offline.client_error==='none',
 'offline-content-unavailable-or-created-a-judgment');"""
if text.count(before_assert)!=1 or after_assert in text:
    raise SystemExit("BLOCKED: historical offline acceptance shape changed")
text=text.replace(before_assert,after_assert)
path.write_text(text)
print(json.dumps({'witness_source':'pinned-deployed-baseline',
  'witness_patch':'wait-for-document-complete-and-boolean-only-failure-diagnostic',
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
