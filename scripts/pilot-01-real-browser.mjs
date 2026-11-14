#!/usr/bin/env node
// Pilot 01: real Chromium + real HTTP gateway, disposable GitHub Actions only.
// User actions use the original served web/index.html, without mocked transport.
// No production token, user data, external host write, or operator volume is used.
import {spawn, execFileSync} from 'node:child_process';
import {mkdtemp, mkdir, readdir, readFile, rm} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import os from 'node:os';
import path from 'node:path';

const ORIGIN = 'http://127.0.0.1:3000';
const token = process.env.NEXUS_API_TOKEN;
const container = process.env.PILOT_CONTAINER_NAME;
const browser = process.env.PILOT_BROWSER;
const runId = process.env.GITHUB_RUN_ID;
if (process.env.GITHUB_ACTIONS !== 'true' ||
    process.env.PILOT_DISPOSABLE_CONTAINER !== 'true' ||
    !/^[0-9]+$/.test(runId || '') ||
    container !== 'nexus-pilot-01-' + runId ||
    !browser || !token || token.length < 32 ||
    typeof WebSocket === 'undefined')
  throw new Error('Pilot 01 requires a disposable CI container, Node 22+, and ephemeral credentials');

const SAFE_FAILURE_CODES=new Set(["original-ui-not-loaded", "unloaded-edit-enabled", "real-readiness", "create-workspace", "workspace-not-selected", "claim-record", "alternative-record", "silent-judgment", "explicit-judgment", "workspace-export", "export-not-confirmed", "server-reload-failed", "persisted-data-mismatch", "incorrect-viewport", "browser-exited", "browser-debugger-port", "browser-page-target", "nonlocal-debugger", "debugger-timeout", "debugger-error", "browser-rpc-failure", "browser-rpc-timeout", "browser-page-ready", "browser-closed", "real-browser-download-missing", "download-not-equal-to-server", "readiness-after-restart", "timed-out-ui-action", "fresh-browser-did-not-reset", "backend-allowed-missing-bearer", "missing-auth-granted-access", "UI-state-not-restored", "persisted-get", "human-judgment-lost", "viewport", "restart-changed-snapshot", "pilot-browser-assertion"]);
const sha256 = data => createHash('sha256').update(data).digest('hex');
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const deadline = async (fn, maxMs, label) => {
  const end = Date.now() + maxMs;
  while (Date.now() < end) {
    const value = await fn();
    if (value) return value;
    await delay(100);
  }
  throw new Error(label);
};
async function waitReady() {
  await deadline(async () => {
    try {
      const response = await fetch(ORIGIN + '/readyz', {signal: AbortSignal.timeout(2000)});
      return response.status === 200 && (await response.json()).status === 'ready';
    } catch {return false}
  }, 45000, 'readiness-after-restart');
}
async function openBrowser(layout) {
  const width = layout === 'narrow' ? 390 : 1280;
  const root = await mkdtemp(path.join(os.tmpdir(), 'nexus-pilot-01-'));
  const profile = path.join(root, 'profile');
  const downloads = path.join(root, 'downloads');
  await mkdir(downloads);
  const child = spawn(browser, [
    '--headless', '--no-sandbox', '--disable-dev-shm-usage',
    '--disable-background-networking', '--disable-extensions', '--no-first-run',
    '--no-default-browser-check', '--force-device-scale-factor=1',
    '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=0',
    '--user-data-dir=' + profile, '--window-size=' + width + ',980', ORIGIN + '/'
  ], {stdio: ['ignore', 'ignore', 'ignore']});
  let sock, serial = 0;
  const pending = new Map();
  let started = false;
  const close = async () => {
    for (const req of pending.values()) req.reject(new Error('browser-closed'));
    pending.clear();
    if (sock?.readyState === WebSocket.OPEN) sock.close();
    if (child.pid && child.exitCode === null) child.kill('SIGTERM');
    await delay(350);
    if (child.pid && child.exitCode === null) child.kill('SIGKILL');
    await rm(root, {recursive: true, force: true});
  };
  try {
    const port = await deadline(async () => {
      if (child.exitCode !== null) throw new Error('browser-exited');
      try {
        const p = (await readFile(path.join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0];
        return /^\d+$/.test(p) ? p : null;
      } catch {return null}
    // Real ephemeral CI can have a slow cold Chromium start after the image build.
    }, 30000, 'browser-debugger-port');
    const target = await deadline(async () => {
      try {
        const response = await fetch(`http://127.0.0.1:${port}/json/list`,
          {signal: AbortSignal.timeout(1500)});
        if (!response.ok) return null;
        return (await response.json()).find(item => item.type === 'page' &&
          item.url === ORIGIN + '/');
      } catch {return null}
    }, 12000, 'browser-page-target');
    const debuggerAddress = new URL(target.webSocketDebuggerUrl);
    if (debuggerAddress.hostname !== '127.0.0.1' ||
        debuggerAddress.port !== port) throw new Error('nonlocal-debugger');
    sock = new WebSocket(debuggerAddress);
    await new Promise((resolve, reject) => {
      const t = setTimeout(() => reject(new Error('debugger-timeout')), 5000);
      sock.addEventListener('open', () => {clearTimeout(t); resolve()}, {once: true});
      sock.addEventListener('error', () => {clearTimeout(t); reject(new Error('debugger-error'))}, {once: true});
    });
    sock.addEventListener('message', event => {
      let message;
      try {message = JSON.parse(event.data)} catch {return}
      const req = pending.get(message.id);
      if (!req) return;
      pending.delete(message.id);
      clearTimeout(req.timer);
      if (message.error) req.reject(new Error('browser-rpc-failure'));
      else req.resolve(message.result);
    });
    const rpc = (method, params = {}, ms = 12000) => new Promise((resolve, reject) => {
      const id = ++serial;
      const timer = setTimeout(() => {
        pending.delete(id);
        reject(new Error('browser-rpc-timeout'));
      }, ms);
      pending.set(id, {resolve, reject, timer});
      sock.send(JSON.stringify({id, method, params}));
    });
    const evaluate = async expression => {
      const result = await rpc('Runtime.evaluate', {
        expression, awaitPromise: true, returnByValue: true
      }, 65000);
      if (result.exceptionDetails || !result.result || result.result.value === undefined)
        throw new Error('pilot-browser-assertion');
      const data = result.result.value;
      if (data?.status !== 'PASS') throw new Error(SAFE_FAILURE_CODES.has(data?.failure_code)?data.failure_code:'pilot-browser-assertion');
      return data;
    };
    await rpc('Page.setDownloadBehavior', {behavior: 'allow', downloadPath: downloads});
    await deadline(async () => {
      try {
        const result = await rpc('Runtime.evaluate', {
          expression: "document.readyState === 'complete' && Boolean(document.getElementById('createWorkspaceButton'))",
          returnByValue: true
        });
        return result.result?.value === true;
      } catch {return false}
    }, 12000, 'browser-page-ready');
    started = true;
    return {root, downloads, evaluate, close, width};
  } catch (error) {await close(); throw error}
}
function createScript(workspace, layout) {
  return `(async () => {
    const token = ${JSON.stringify(token)}, id = ${JSON.stringify(workspace)};
    const node = name => document.getElementById(name);
    const assert = (ok, label) => {if (!ok) throw new Error(label)};
    const wait = async (fn, label) => {
      for (let i = 0; i < 260; i++) {
        if (fn()) return;
        await new Promise(resolve => setTimeout(resolve, 50));
      }
      throw new Error(label);
    };
    const set = (name, value) => {
      node(name).value = value;
      node(name).dispatchEvent(new Event('input', {bubbles: true}));
    };
    const use = async (button, message, label) => {
      node(button).click();
      await wait(() => node('status').textContent.includes(message), label);
    };
    try {
      assert(node('token') && node('question'), 'original-ui-not-loaded');
      assert(node('addClaimButton').disabled &&
        node('recordJudgmentButton').disabled, 'unloaded-edit-enabled');
      node('readinessButton').click();
      await wait(() => node('readinessResult').textContent.includes('Service reported ready'),
        'real-readiness');
      set('token', token);
      set('workspaceId', id);
      set('provenance', 'pilot:synthetic');
      set('question', 'Pilot 01 synthetic judgment question');
      await use('createWorkspaceButton', 'Workspace created.', 'create-workspace');
      assert(node('connection').textContent.includes(id), 'workspace-not-selected');
      assert(node('judgmentView').textContent.includes('No human judgment'), 'premature-judgment');
      set('claimText', 'Synthetic evidence requires scrutiny');
      set('claimOrigin', 'external_evidence');
      set('claimSource', 'pilot:synthetic-source');
      set('claimUncertainty', 'high');
      await use('addClaimButton', 'Claim recorded.', 'claim-record');
      set('altLabel', 'Inspect alternatives');
      set('altConsequences', 'Uncertainty remains');
      await use('addAlternativeButton', 'Alternative recorded.', 'alternative-record');
      assert(node('judgmentView').textContent.includes('No human judgment'), 'silent-judgment');
      set('decision', 'Synthetic human judgment');
      set('rationale', 'Explicit pilot decision only');
      await use('recordJudgmentButton', 'Human judgment transition recorded.', 'explicit-judgment');
      await use('backupWorkspaceButton', 'Fresh server snapshot downloaded.', 'workspace-export');
      assert(node('backupStatus').textContent.includes('Backup downloaded'), 'export-not-confirmed');
      const response = await fetch('/v1/workspaces/' + encodeURIComponent(id),
        {headers: {authorization: 'Bearer ' + token}, cache: 'no-store'});
      assert(response.status === 200, 'server-reload-failed');
      const snapshot = await response.json();
      assert(snapshot.workspace.id === id &&
        snapshot.workspace.judgment.decision === 'Synthetic human judgment' &&
        snapshot.workspace.claims.length === 1 &&
        snapshot.workspace.alternatives.length === 1 &&
        snapshot.events.length >= 4, 'persisted-data-mismatch');
      const bytes = new TextEncoder().encode(JSON.stringify(snapshot));
      const digest = [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))]
        .map(b => b.toString(16).padStart(2, '0')).join('');
      const actualWidth = window.innerWidth;
      assert((${layout === 'narrow'} && actualWidth <= 760) ||
        (${layout === 'wide'} && actualWidth > 760), 'incorrect-viewport');
      return {status:'PASS', checks:['real-readiness','create-workspace','record-source',
        'record-alternative','no-auto-judgment','explicit-human-judgment',
        'browser-json-export','authenticated-server-reload'],
        snapshot_sha256:digest, events:snapshot.events.length, width:actualWidth};
    } catch (error) {return {status:'FAIL',failure_code:${JSON.stringify([...SAFE_FAILURE_CODES])}.includes(error?.message)?error.message:'pilot-browser-assertion'};}
  })()`;
}
function reloadScript(workspace, layout) {
  return `(async () => {
    const token = ${JSON.stringify(token)}, id = ${JSON.stringify(workspace)};
    const node = name => document.getElementById(name);
    const wait = async (fn) => {
      for (let i = 0; i < 260; i++) {
        if (fn()) return;
        await new Promise(resolve => setTimeout(resolve, 50));
      }
      throw new Error('timed-out-ui-action');
    };
    const set = (name, value) => {
      node(name).value = value;
      node(name).dispatchEvent(new Event('input', {bubbles: true}));
    };
    try {
      if (!node('loadWorkspaceButton') || !node('addClaimButton').disabled)
        throw new Error('fresh-browser-did-not-reset');
      set('workspaceId', id);
      const rejected = await fetch('/v1/workspaces/' + encodeURIComponent(id),
        {cache:'no-store'});
      if (rejected.status !== 401) throw new Error('backend-allowed-missing-bearer');
      node('loadWorkspaceButton').click();
      await wait(() => node('status').textContent.includes('Authentication required.'));
      if (!node('addClaimButton').disabled) throw new Error('missing-auth-granted-access');
      set('token', token);
      node('loadWorkspaceButton').click();
      await wait(() => node('status').textContent.includes('Workspace loaded.'));
      if (!node('claims').textContent.includes('Synthetic evidence') ||
          !node('alts').textContent.includes('Inspect alternatives') ||
          !node('judgmentView').textContent.includes('Synthetic human judgment') ||
          !node('history').textContent.includes('provenance'))
        throw new Error('UI-state-not-restored');
      const response = await fetch('/v1/workspaces/' + encodeURIComponent(id),
        {headers: {authorization: 'Bearer ' + token}, cache:'no-store'});
      if (response.status !== 200) throw new Error('persisted-get');
      const snapshot = await response.json();
      const digest = [...new Uint8Array(await crypto.subtle.digest('SHA-256',
        new TextEncoder().encode(JSON.stringify(snapshot))))].map(b =>
        b.toString(16).padStart(2, '0')).join('');
      if (!snapshot.workspace.judgment ||
          snapshot.workspace.judgment.decision !== 'Synthetic human judgment')
        throw new Error('human-judgment-lost');
      const width = window.innerWidth;
      if ((${layout === 'narrow'} && width > 760) ||
          (${layout === 'wide'} && width <= 760)) throw new Error('viewport');
      return {status:'PASS', checks:['missing-bearer-denied','browser-context-reloaded',
        'real-workspace-survived-restart','human-judgment-retained','audit-visible'],
        snapshot_sha256:digest, events:snapshot.events.length, width};
    } catch (error) {return {status:'FAIL',failure_code:${JSON.stringify([...SAFE_FAILURE_CODES])}.includes(error?.message)?error.message:'pilot-browser-assertion'};}
  })()`;
}
let phase = 'bootstrap';
try {
  const reports = [];
  await waitReady();
  for (const layout of ['narrow', 'wide']) {
    const workspace = 'pilot-01-' + runId + '-' + layout;
    phase = 'browser-create-' + layout;
    let session = await openBrowser(layout);
    let created;
    try {
      created = await session.evaluate(createScript(workspace, layout));
      const file = await deadline(async () => {
        const files = (await readdir(session.downloads)).filter(n =>
          n.startsWith('nexus-backup-' + workspace + '-') &&
          n.endsWith('.json'));
        return files.length === 1 ? path.join(session.downloads, files[0]) : null;
      }, 10000, 'real-browser-download-missing');
      const exported = JSON.parse(await readFile(file, 'utf8'));
      if (sha256(JSON.stringify(exported)) !== created.snapshot_sha256)
        throw new Error('download-not-equal-to-server');
    } finally {await session.close()}
    phase = 'disposable-container-restart-' + layout;
    // No operator deployment or volume. Unique synthetic CI container only.
    execFileSync('docker', ['restart', container], {stdio: 'ignore', timeout: 40000});
    await waitReady();
    phase = 'browser-reopen-' + layout;
    session = await openBrowser(layout);
    let reloaded;
    try {reloaded = await session.evaluate(reloadScript(workspace, layout))}
    finally {await session.close()}
    if (created.snapshot_sha256 !== reloaded.snapshot_sha256 ||
        created.events !== reloaded.events)
      throw new Error('restart-changed-snapshot');
    reports.push({layout, width: created.width, checks: [...created.checks, ...reloaded.checks],
      snapshot_integrity_sha256: created.snapshot_sha256,
      events: created.events, survived_process_restart: true,
      browser_export_equal_to_server: true, human_judgment_explicit: true});
  }
  process.stdout.write(JSON.stringify({schema:'nexus.pilot-01.real-browser-gateway.v1',
    status:'PASS', scope:'synthetic-disposable-ci-only', browser:'real-headless-chromium',
    transport:'real-loopback-http', origin:'localhost_only', separate_volumes:false,
    layouts:reports, live_railway_tested:false, human_user_tested:false,
    independent_production_backup_verified:false, deployment_changed:false,
    release_authority:'none', seal:false}) + '\n');
} catch (error) {
  process.stdout.write(JSON.stringify({schema:'nexus.pilot-01.real-browser-gateway.v1',
    status:'FAIL', stage:phase, failure_code:SAFE_FAILURE_CODES.has(error?.message)?error.message:'pilot-browser-assertion', scope:'synthetic-disposable-ci-only',
    live_railway_tested:false, release_authority:'none', seal:false}) + '\n');
  process.exitCode = 1;
}
