#!/usr/bin/env python3
"""Real Chromium DOM/layout witness. Synthetic in-page transport, never a live API."""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

BOOTSTRAP = r'''
window.nexusBrowserWitness = (() => {
  const calls = [];
  let deferred = null;
  const snapshot = id => ({schema_version: 1, workspace: {id, question: 'Question ' + id,
    claims: [{text: '<img src=x onerror="window.untrustedMarkupRan=true">',
      origin: {kind: 'external_evidence', source: 'synthetic'}, uncertainty: 'unknown'}],
    alternatives: [], judgment: null}, events: []});
  window.fetch = async (path, options = {}) => {
    calls.push({path, method: options.method || 'GET', body: options.body});
    let value;
    if (deferred) {const next = deferred; deferred = null; value = await next;}
    else if (path === '/readyz') value = {httpResponse: {status: 503, json: async () => ({status: 'quarantined'})}};
    else if (path.startsWith('/v1/requests/')) {
      const id = decodeURIComponent(path.slice('/v1/requests/'.length));
      if (id === 'missing' || id === 'unauthorized') value = {httpResponse: {
        ok: false, status: id === 'missing' ? 404 : 401,
        json: async () => ({error: 'synthetic-status-error'})}};
      else value = {request_id: id, status: id === 'uncertain' ? 'indeterminate' : 'pending'};
    }
    else if (path === '/v1/workspaces/import') value = JSON.parse(options.body);
    else value = snapshot(decodeURIComponent(path.split('/')[3]));
    return value?.httpResponse ?? {ok: true, status: 200, json: async () => value};
  };
  return {calls, snapshot, defer() {let resolve; deferred = new Promise(r => {resolve = r}); return resolve;}};
})();
window.nexusBrowserErrors = [];
window.addEventListener('error', event => window.nexusBrowserErrors.push(event.message));
window.addEventListener('unhandledrejection', event => window.nexusBrowserErrors.push(String(event.reason)));
'''

SCENARIOS = r'''
window.addEventListener('load', async () => {
  const output = document.getElementById('nexus-browser-result');
  const checks = [];
  const node = id => document.getElementById(id);
  const assert = (ok, message) => {if (!ok) throw new Error(message)};
  const tick = () => new Promise(resolve => setTimeout(resolve, 0));
  const choose = id => {node('workspaceId').value = id; node('workspaceId').dispatchEvent(new Event('input', {bubbles: true}));};
  const drafts = ['claimText', 'claimSource', 'altLabel', 'altConsequences', 'decision', 'rationale'];
  const edits = ['addClaimButton', 'addAlternativeButton', 'recordJudgmentButton', 'backupWorkspaceButton'];
  const fill = () => drafts.forEach(id => {node(id).value = 'Draft ' + id;});
  const load = async id => {choose(id); node('loadWorkspaceButton').click(); await tick();};
  const lab = window.nexusBrowserWitness;
  try {
    assert(edits.every(id => node(id).disabled), 'unloaded editing was enabled');
    await load('A'); fill(); choose('B');
    assert(edits.every(id => node(id).disabled), 'mismatched editing was enabled');
    node('recordJudgmentButton').click(); await recordJudgment();
    assert(lab.calls.length === 1, 'mismatch sent transport');
    await load('B');
    assert(drafts.every(id => node(id).value === ''), 'cross-workspace drafts survived');
    assert(node('question').value === 'Question B', 'wrong workspace displayed');
    node('decision').value = 'Explicit decision for B'; node('recordJudgmentButton').click(); await tick();
    assert(lab.calls.filter(c => c.method === 'POST').length === 1, 'unexpected judgment writes');
    assert(lab.calls.at(-1).path === '/v1/workspaces/B/judgment', 'judgment targeted wrong workspace');
    checks.push('selection-and-explicit-judgment');

    const resolveLoad = lab.defer(); choose('C'); node('loadWorkspaceButton').click();
    const count = lab.calls.length; choose('D'); node('loadWorkspaceButton').click();
    assert(lab.calls.length === count, 'second operation started while busy');
    resolveLoad(lab.snapshot('C')); await tick();
    assert(node('workspaceId').value === 'D', 'late load changed selected ID');
    assert(node('question').value === 'Question B', 'late load replaced displayed workspace');
    assert(edits.every(id => node(id).disabled), 'late load enabled wrong edits');
    checks.push('late-load-rejected');

    await load('D'); fill(); const resolveWrite = lab.defer();
    const beforeWrite = lab.calls.length;
    node('recordJudgmentButton').click(); node('recordJudgmentButton').click();
    assert(lab.calls.length === beforeWrite + 1, 'duplicate click sent duplicate write');
    choose('E'); resolveWrite(lab.snapshot('D')); await tick();
    assert(node('workspaceId').value === 'E', 'late write changed selected ID');
    assert(node('question').value === 'Question D', 'late write replaced displayed state');
    assert(node('status').textContent.includes('may have taken effect'), 'uncertain sent write hidden');
    assert(lab.calls.length === beforeWrite + 1, 'write was automatically retried');
    checks.push('late-write-and-double-click');

    await load('E'); fill();
    const transfer = new DataTransfer();
    transfer.items.add(new File([JSON.stringify(lab.snapshot('F'))], 'synthetic.json', {type: 'application/json'}));
    node('importFile').files = transfer.files;
    node('importFile').dispatchEvent(new Event('change', {bubbles: true}));
    // File.text() is a real browser read; allow bounded task turns for completion.
    for (let n = 0; n < 100 && node('loadWorkspaceButton').disabled; n++) await new Promise(r => setTimeout(r, 20));
    assert(node('workspaceId').value === 'F', 'file import did not adopt returned context: ' + node('status').textContent);
    assert(drafts.every(id => node(id).value === ''), 'import preserved wrong-context drafts');
    assert(node('importFile').value === '', 'file input was not reset');
    checks.push('real-file-input-import');

    assert(node('claims').textContent.includes('<img'), 'evidence text missing');
    assert(!node('claims').querySelector('img') && !window.untrustedMarkupRan, 'evidence became executable markup');
    checks.push('evidence-rendered-as-text');

    node('readinessButton').click(); await tick();
    assert(node('readinessResult').textContent.includes('Writes are blocked'), 'quarantine observation missing');
    assert(node('readinessResult').getAttribute('aria-live') === 'polite', 'readiness feedback not announced');
    assert(lab.calls.at(-1).path === '/readyz' && lab.calls.at(-1).method === 'GET', 'readiness sent a mutation');
    checks.push('readiness-quarantine-observation');
    await load('auth-context'); fill();
    const oldAuthResponse=lab.defer(); node('loadWorkspaceButton').click();
    const beforeAuthChange=lab.calls.length;
    node('token').value='replacement-token'; node('token').dispatchEvent(new Event('input',{bubbles:true}));
    assert(drafts.every(id=>node(id).value==='') && node('claims').innerHTML==='', 'token change retained workspace content');
    oldAuthResponse(lab.snapshot('auth-context')); await tick();
    assert(edits.every(id=>node(id).disabled), 'late token response enabled editing');
    assert(node('status').textContent.includes('Do not blindly retry'), 'uncertain operation warning missing');
    assert(lab.calls.length===beforeAuthChange, 'token change retried an operation');
    await load('auth-context');
    assert(!node('recordJudgmentButton').disabled, 'new authenticated load did not restore editing');
    checks.push('authentication-context-boundary');
    const statusStart = lab.calls.length;
    const requestId = id => {node('requestLookupId').value = id; node('requestLookupId').dispatchEvent(new Event('input', {bubbles: true}));};
    for (const [id, expected] of [
      ['retained', 'Acceptance recorded (pending). Completion is not established.'],
      ['uncertain', 'Outcome unknown (indeterminate).'],
      ['missing', 'No retained record found. This does not establish whether execution occurred.'],
      ['unauthorized', 'Authentication required.'],
    ]) {
      requestId(id); node('requestLookupButton').click(); await tick();
      assert(node('requestLookupResult').textContent.includes(expected), 'incorrect retained-status meaning for ' + id);
    }
    assert(node('requestLookupResult').getAttribute('aria-live') === 'polite', 'lookup feedback is not announced');
    checks.push('request-status-semantics');

    const lateStatus = lab.defer(); requestId('old-status'); node('requestLookupButton').click();
    const lookupsSent = lab.calls.length;
    requestId('changed-status'); node('requestLookupButton').click();
    lateStatus({request_id: 'old-status', status: 'pending'}); await tick();
    assert(node('requestLookupResult').textContent.includes('changed. Check again'), 'late request status replaced the new selection');
    assert(lab.calls.length === lookupsSent, 'lookup retried automatically or duplicated');
    assert(lab.calls.slice(statusStart).every(call => call.method === 'GET' && call.path.startsWith('/v1/requests/')), 'lookup sent a mutation');
    checks.push('request-status-stale-read');


    await load('response-target'); fill();
    for (const button of ['loadWorkspaceButton','recordJudgmentButton','backupWorkspaceButton']) {
      const before = lab.calls.length, wrong = lab.defer();
      node(button).click(); wrong(lab.snapshot('unexpected-response')); await tick();
      assert(node('workspaceId').value === 'response-target', 'response redirected selected workspace');
      assert(node('question').value === 'Question response-target', 'wrong response replaced content');
      assert(node('status').textContent.includes('unexpected workspace'), 'response mismatch warning missing');
      assert(lab.calls.length === before + 1, 'mismatch retried transport');
    }
    const wrongImport = lab.defer();
    const importing = importWorkspace(new File([JSON.stringify(lab.snapshot('file-target'))], 'synthetic.json'));
    // Real File.text() completes asynchronously before transport can resolve.
    wrongImport(lab.snapshot('unexpected-response')); await importing;
    assert(node('workspaceId').value === 'response-target', 'import accepted wrong response ID');
    assert(node('backupStatus').textContent.includes('unexpected workspace'), 'import mismatch warning missing');
    checks.push('workspace-response-target');

    const first = node('claims').closest('section').getBoundingClientRect();
    const second = node('alts').closest('section').getBoundingClientRect();
    const narrow = window.innerWidth <= 760;
    assert(document.documentElement.scrollWidth <= window.innerWidth, 'horizontal overflow');
    if (narrow) assert(Math.abs(first.left - second.left) < 1 && second.top > first.top, 'narrow layout did not stack');
    else assert(second.left > first.left + 10 && Math.abs(first.top - second.top) < 1, 'wide layout did not form columns');
    assert(window.nexusBrowserErrors.length === 0, 'page errors: ' + window.nexusBrowserErrors.join('; '));
    checks.push(narrow ? 'narrow-layout' : 'wide-layout');
    output.textContent = JSON.stringify({status: 'PASS', checks, width: window.innerWidth,
      transport: 'synthetic-in-page-only', authority: 'none', production_verified: false});
  } catch (error) {
    output.textContent = JSON.stringify({status: 'FAIL', checks, error: String(error)});
  }
});
'''


def main():
    browser = next((shutil.which(name) for name in
                    ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser')
                    if shutil.which(name)), None)
    if browser is None:
        raise RuntimeError('real browser unavailable; DOM/layout witness did not run')
    version = subprocess.run([browser, '--version'], check=True, capture_output=True,
                             text=True, timeout=10).stdout.strip()
    html = (Path(__file__).resolve().parents[1] / 'web/index.html').read_text()
    # Instrument only this disposable copy; the application file is unchanged.
    html = html.replace('<script>', '<script>' + BOOTSTRAP + '</script><script>', 1)
    html = html.replace('</body>', '<pre id="nexus-browser-result" hidden></pre><script>' +
                        SCENARIOS + '</script></body>')
    reports = []
    with tempfile.TemporaryDirectory(prefix='nexus-real-browser-') as temporary:
        root = Path(temporary)
        page = root / 'witness.html'
        page.write_text(html)
        for name, dimensions in [('narrow', '500,1000'), ('wide', '1280,1000')]:
            runner = Path(__file__).with_name('workspace-browser-runner.mjs')
            result = subprocess.run(['node', str(runner), browser, page.as_uri(),
                                     str(root / name), dimensions], capture_output=True,
                                    text=True, timeout=45)
            if result.returncode:
                raise RuntimeError('real browser process failed: ' + result.stderr[-2000:])
            report = json.loads(result.stdout)
            if report.get('status') != 'PASS' or len(report.get('checks', [])) != 11:
                raise RuntimeError('browser witness failed: ' + json.dumps(report, sort_keys=True))
            if (name == 'narrow') != (report['width'] <= 760):
                raise RuntimeError('browser did not exercise the requested layout class')
            reports.append({'layout': name, **report})
    print(json.dumps({'schema': 'nexus.workspace-browser-witness.v1', 'status': 'PASS',
                      'browser': version, 'reports': reports, 'authority': 'none',
                      'scope': 'real-browser-synthetic-transport-only'}, sort_keys=True))


if __name__ == '__main__':
    main()
