#!/usr/bin/env node
// Execute the actual inline application code with a bounded synthetic DOM/transport.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const html = fs.readFileSync(fileURLToPath(new URL('../web/index.html', import.meta.url)), 'utf8');
const code = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const draftIds = ['claimText', 'claimSource', 'altLabel', 'altConsequences', 'decision', 'rationale'];
const editIds = ['addClaimButton', 'addAlternativeButton', 'recordJudgmentButton', 'backupWorkspaceButton'];
const fixture = id => ({schema_version: 1, workspace: {id, question: `Question ${id}`,
  claims: [{text: `Claim ${id}`, origin: {kind: 'human'}, uncertainty: 'unknown'}],
  alternatives: [], judgment: null}, events: []});
const deferred = () => {let resolve; const promise = new Promise(r => {resolve = r}); return {promise, resolve}};

function app() {
  const elements = new Map();
  for (const [, id] of html.matchAll(/\bid="([^"]+)"/g)) {
    assert(!elements.has(id), `duplicate DOM ID: ${id}`);
    elements.set(id, {value: '', textContent: '', innerHTML: '', disabled: false});
  }
  const element = id => {assert(elements.has(id), `missing DOM ID: ${id}`); return elements.get(id)};
  element('claimOrigin').value = 'human'; element('claimUncertainty').value = 'unknown';
  element('provenance').value = 'human:owner'; element('token').value = 'synthetic-token';
  const calls = [], downloads = [];
  let transport = async path => fixture(decodeURIComponent(path.split('/').at(-1)));
  const context = vm.createContext({
    document: {getElementById: element, body: {appendChild() {}}, createElement() {
      return {click() {downloads.push(this.download)}, remove() {}};
    }},
    fetch: async (path, options) => {
      calls.push({path, options});
      const value = await transport(path, options);
      return value?.httpResponse ?? {ok: true, status: 200, json: async () => value};
    },
    Blob, URL: {createObjectURL: () => 'blob:synthetic', revokeObjectURL() {}},
    setTimeout, clearTimeout, AbortController, TextEncoder, console,
  });
  vm.runInContext(code, context, {timeout: 1000});
  return {element, calls, downloads,
    run: expression => vm.runInContext(expression, context, {timeout: 1000}),
    transport: handler => {transport = handler},
    select(id) {element('workspaceId').value = id; context.workspaceSelectionChanged()},
    async load(id) {this.select(id); await context.loadWorkspace()},
    fill() {for (const id of draftIds) element(id).value = `Draft ${id}`},
  };
}

test('selection mismatch blocks all edit/export actions before transport', async () => {
  const a = app();
  for (const id of editIds) assert.equal(a.element(id).disabled, true);
  await a.load('A'); a.fill(); a.select('B');
  for (const id of editIds) assert.equal(a.element(id).disabled, true);
  for (const action of ['addClaim()', 'addAlternative()', 'recordJudgment()', 'backupWorkspace()']) await a.run(action);
  assert.equal(a.calls.length, 1);
  assert.equal(a.downloads.length, 0);
  assert.equal(a.run('snapshot.workspace.id'), 'A');
  assert.match(a.element('connection').textContent, /Loaded: A/);
  assert.match(a.element('status').textContent, /Load the selected workspace/);
  // Programmatic field changes cannot bypass the action guard either.
  a.element('workspaceId').value = 'C';
  await a.run('recordJudgment()');
  assert.equal(a.calls.length, 1);
});

test('loading another workspace clears drafts and new judgment targets that workspace', async () => {
  const a = app(); await a.load('A'); a.fill(); await a.load('B');
  for (const id of draftIds) assert.equal(a.element(id).value, '');
  assert.equal(a.element('question').value, 'Question B');
  assert.match(a.element('claims').innerHTML, /Claim B/);
  assert.doesNotMatch(a.element('claims').innerHTML, /Claim A/);
  for (const id of editIds) assert.equal(a.element(id).disabled, false);
  a.element('decision').value = 'New decision for B';
  a.transport(async () => fixture('B'));
  await a.run('recordJudgment()');
  const sent = a.calls.at(-1);
  assert.equal(sent.path, '/v1/workspaces/B/judgment');
  assert.equal(JSON.parse(sent.options.body).decision, 'New decision for B');
  assert.equal(a.calls.filter(c => c.options.method === 'POST').length, 1);
});

test('refreshing the same workspace preserves drafts without submitting them', async () => {
  const a = app(); await a.load('A'); a.fill(); await a.run('loadWorkspace()');
  for (const id of draftIds) assert.equal(a.element(id).value, `Draft ${id}`);
  assert.equal(a.calls.length, 2);
  assert(a.calls.every(c => c.options.method === undefined));
});

test('late load responses cannot replace a changed selection or start a second request', async () => {
  const a = app(); const pending = deferred(); a.select('A');
  a.transport(() => pending.promise);
  const first = a.run('loadWorkspace()');
  assert.equal(a.element('loadWorkspaceButton').disabled, true);
  a.select('B'); await a.run('loadWorkspace()');
  assert.equal(a.calls.length, 1);
  pending.resolve(fixture('A')); await first;
  assert.equal(a.element('workspaceId').value, 'B');
  assert.equal(a.run('snapshot'), null);
  assert.match(a.element('status').textContent, /selection changed/);
  for (const id of editIds) assert.equal(a.element(id).disabled, true);
  a.transport(async () => fixture('B')); await a.run('loadWorkspace()');
  assert.equal(a.run('snapshot.workspace.id'), 'B');
});

test('in-flight writes keep their original target, ignore stale display responses, and never auto-retry', async () => {
  const a = app(); await a.load('A'); a.fill(); const pending = deferred();
  a.transport(() => pending.promise);
  const write = a.run('recordJudgment()');
  await a.run('recordJudgment()'); // Duplicate click while busy.
  assert.equal(a.calls.length, 2);
  assert.equal(a.calls.at(-1).path, '/v1/workspaces/A/judgment');
  a.select('B'); pending.resolve(fixture('A')); await write;
  assert.equal(a.element('workspaceId').value, 'B');
  assert.equal(a.run('snapshot.workspace.id'), 'A');
  assert.match(a.element('status').textContent, /may have taken effect/);
  assert.equal(a.calls.length, 2);
  for (const id of editIds) assert.equal(a.element(id).disabled, true);
});

test('selection changes during file reading prevent import before any write is sent', async () => {
  const a = app(); await a.load('A'); const reading = deferred();
  // Supply the file through the VM, without a disk or a real user archive.
  const file = {text: () => reading.promise};
  a.transport(async () => {throw new Error('unexpected import transport')});
  const importing = a.run('importWorkspace')(file);
  a.select('B'); reading.resolve(JSON.stringify(fixture('C'))); await importing;
  assert.equal(a.calls.length, 1);
  assert.equal(a.element('workspaceId').value, 'B');
  assert.equal(a.run('snapshot.workspace.id'), 'A');
  assert.equal(a.element('importFile').value, '');
});

test('successful create/import switches context and export remains explicitly user-triggered', async () => {
  const a = app(); await a.load('A'); a.fill(); a.select('B');
  a.transport(async () => fixture('B')); await a.run('createWorkspace()');
  for (const id of draftIds) assert.equal(a.element(id).value, '');
  assert.equal(a.run('snapshot.workspace.id'), 'B');
  a.fill(); a.transport(async () => fixture('C'));
  await a.run('importWorkspace')({text: async () => JSON.stringify(fixture('C'))});
  assert.equal(a.run('snapshot.workspace.id'), 'C');
  for (const id of draftIds) assert.equal(a.element(id).value, '');
  assert.equal(a.downloads.length, 0);
  await a.run('backupWorkspace()');
  assert.equal(a.downloads.length, 1);
  assert.match(a.downloads[0], /^nexus-backup-C-/);
});

test('request lookup uses only GET and distinguishes pending from indeterminate', async () => {
  const a = app(); a.element('requestLookupId').value = 'retained-id';
  for (const status of ['pending', 'indeterminate']) {
    a.transport(async () => ({request_id: 'retained-id', status}));
    await a.run('inspectRequest()');
    const message = a.element('requestLookupResult').textContent;
    assert.match(message, status === 'pending' ? /Acceptance recorded.*Completion is not established/ : /Outcome unknown.*Do not blindly resubmit/);
  }
  assert(a.calls.every(c => c.options.method === 'GET' && c.options.cache === 'no-store'));
  assert.equal(a.run('snapshot'), null);
  assert.equal(a.downloads.length, 0);
});

test('request lookup rejects errors, mismatched IDs and invented completion states without echoing payloads', async () => {
  const a = app(); a.element('requestLookupId').value = 'expected';
  const cases = [
    [{httpResponse: {ok: false, status: 401, json: async () => ({error: 'private-server-text'})}}, /Authentication required/],
    [{httpResponse: {ok: false, status: 404, json: async () => ({error: 'private-server-text'})}}, /No retained record.*does not establish whether execution occurred/],
    [{httpResponse: {ok: false, status: 503, json: async () => ({error: 'private-server-text'})}}, /Status unavailable.*Outcome remains unknown/],
    [{request_id: 'different', status: 'pending'}, /Invalid status response.*Outcome remains unknown/],
    [{request_id: 'expected', status: 'completed'}, /Invalid status response.*Outcome remains unknown/],
    [{httpResponse: {ok: true, status: 200, json: async () => {throw new SyntaxError('private-server-text')}}}, /Invalid status response/],
  ];
  for (const [response, message] of cases) {
    a.transport(async () => response); await a.run('inspectRequest()');
    assert.match(a.element('requestLookupResult').textContent, message);
    assert.doesNotMatch(a.element('requestLookupResult').textContent, /private-server-text/);
  }
  a.transport(async () => {throw new Error('private-server-text')});
  await a.run('inspectRequest()');
  assert.match(a.element('requestLookupResult').textContent, /Unable to read.*Outcome remains unknown/);
  assert(a.calls.every(c => c.options.method === 'GET'));
});

test('request lookup keeps IDs opaque and applies the durable UTF-8 byte bound before transport', async () => {
  const a = app();
  for (const id of ['', 'é'.repeat(51), 'x'.repeat(101)]) {
    a.element('requestLookupId').value = id; await a.run('inspectRequest()');
    assert.match(a.element('requestLookupResult').textContent, /1–100 UTF-8 bytes/);
  }
  assert.equal(a.calls.length, 0);
  const exact = ' space/é ';
  a.element('requestLookupId').value = exact;
  a.transport(async () => ({request_id: exact, status: 'pending'}));
  await a.run('inspectRequest()');
  assert.equal(a.calls[0].path, '/v1/requests/' + encodeURIComponent(exact));
  assert.match(a.element('requestLookupResult').textContent, /Acceptance recorded/);
});

test('request ID or token changes invalidate late lookups and duplicate clicks never submit', async () => {
  for (const change of ['id', 'token', 'programmatic-token']) {
    const a = app(); const pending = deferred();
    a.element('requestLookupId').value = 'old'; a.transport(() => pending.promise);
    const first = a.run('inspectRequest()');
    assert.equal(a.element('requestLookupButton').disabled, true);
    await a.run('inspectRequest()'); assert.equal(a.calls.length, 1);
    if (change === 'id') a.element('requestLookupId').value = 'new';
    else a.element('token').value = 'new-token';
    if (change !== 'programmatic-token') a.run('invalidateRequestLookup()');
    pending.resolve({request_id: 'old', status: 'pending'}); await first;
    assert.match(a.element('requestLookupResult').textContent, /changed.*Check again/);
    assert.doesNotMatch(a.element('requestLookupResult').textContent, /Acceptance recorded/);
    assert.equal(a.element('requestLookupButton').disabled, false);
    assert.equal(a.calls.length, 1);
  }
});

test('request lookup aborts a timed-out read without retrying and releases its button', async () => {
  const a = app(); a.element('requestLookupId').value = 'slow';
  a.run('globalThis.setTimeout = callback => { globalThis.expireLookup = callback; return 1 }; globalThis.clearTimeout = () => {}');
  a.transport(async (path, options) => new Promise((resolve, reject) => {
    options.signal.addEventListener('abort', () => {
      const error = new Error('synthetic timeout'); error.name = 'AbortError'; reject(error);
    });
  }));
  const lookup = a.run('inspectRequest()'); a.run('expireLookup()'); await lookup;
  assert.match(a.element('requestLookupResult').textContent, /timed out.*Outcome remains unknown/);
  assert.equal(a.calls.length, 1);
  assert.equal(a.element('requestLookupButton').disabled, false);
});


test('readiness requires the exact HTTP/status pair and sends no credentials or mutations', async () => {
  const a = app();
  for (const [http, status, expected] of [[200,'ready',/reported ready/],[503,'quarantined',/Writes are blocked/],[200,'quarantined',/unknown/],[503,'ready',/unknown/],[500,'private-server-text',/unknown/]]) {
    a.transport(async () => ({httpResponse:{status:http,json:async()=>({status})}}));
    await a.run('inspectReadiness()');
    assert.match(a.element('readinessResult').textContent,expected);
    assert.doesNotMatch(a.element('readinessResult').textContent,/private-server-text/);
    assert.equal(a.element('readinessButton').disabled,false);
  }
  for(const c of a.calls){assert.equal(c.path,'/readyz');assert.equal(c.options.method,'GET');assert.equal(c.options.cache,'no-store');assert.equal(c.options.credentials,'omit');assert.equal(c.options.headers,undefined)}
  assert.equal(a.run('snapshot'),null);
});

test('readiness is single-flight, never retries, and releases after malformed JSON or abort', async () => {
  const a=app(), pending=deferred();a.transport(()=>pending.promise);
  const first=a.run('inspectReadiness()');await a.run('inspectReadiness()');assert.equal(a.calls.length,1);
  pending.resolve({httpResponse:{status:200,json:async()=>{throw new Error('private')}}});await first;
  assert.match(a.element('readinessResult').textContent,/unknown/);
  a.run('globalThis.setTimeout = callback => {globalThis.expireReady=callback;return 1};globalThis.clearTimeout=()=>{}');
  a.transport(async (path,options)=>new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>{const e=new Error();e.name='AbortError';reject(e)})));
  const slow=a.run('inspectReadiness()');a.run('expireReady()');await slow;
  assert.match(a.element('readinessResult').textContent,/timed out/);assert.equal(a.calls.length,2);assert.equal(a.element('readinessButton').disabled,false);
});


test('token input clears loaded data and drafts and requires a new authenticated load', async () => {
  const a=app();await a.load('A');a.fill();
  a.element('token').value='replacement';a.run('authenticationChanged()');
  assert.equal(a.run('snapshot'),null);
  for(const id of [...draftIds,'question'])assert.equal(a.element(id).value,'');
  for(const id of ['claims','alts','judgmentView','history'])assert.equal(a.element(id).innerHTML,'');
  for(const id of editIds)assert.equal(a.element(id).disabled,true);
  await a.run('recordJudgment()');await a.run('backupWorkspace()');assert.equal(a.calls.length,1);assert.equal(a.downloads.length,0);
  await a.load('A');assert.equal(a.calls.at(-1).options.headers.authorization,'Bearer replacement');
  assert.equal(a.element('recordJudgmentButton').disabled,false);
});

test('late load, write and export responses cannot cross an authentication change', async () => {
  for(const action of ['loadWorkspace()','addClaim()','backupWorkspace()'])for(const input of [true,false]){
    const a=app();await a.load('A');a.fill();const pending=deferred();a.transport(()=>pending.promise);
    const task=a.run(action);assert.equal(a.calls.length,2);
    a.element('token').value='replacement';if(input)a.run('authenticationChanged()');
    pending.resolve(fixture('A'));await task;
    assert.equal(a.run('snapshot'),null);assert.equal(a.downloads.length,0);assert.equal(a.calls.length,2);
    assert.match(a.element('status').textContent,/changed.*may have taken effect.*Do not blindly retry/i);
    assert.equal(a.element('recordJudgmentButton').disabled,true);
  }
});

test('programmatic token changes block loaded edits and token switch-back invalidates pending reads', async () => {
  const a=app();await a.load('A');a.fill();a.element('token').value='other';
  await a.run('recordJudgment()');await a.run('backupWorkspace()');assert.equal(a.calls.length,1);
  a.element('token').value='synthetic-token';const pending=deferred();a.transport(()=>pending.promise);
  const task=a.run('loadWorkspace()');
  a.element('token').value='other';a.run('authenticationChanged()');
  a.element('token').value='synthetic-token';a.run('authenticationChanged()');
  pending.resolve(fixture('A'));await task;assert.equal(a.run('snapshot'),null);assert.equal(a.calls.length,2);
});

test('token change while reading an import file stops the write before transport', async () => {
  const a=app();await a.load('A');
  a.run('globalThis.pendingFile={text:()=>new Promise(resolve=>{globalThis.finishFile=resolve})}');
  const task=a.run('importWorkspace(pendingFile)');
  a.element('token').value='replacement';a.run('authenticationChanged()');
  a.run('finishFile('+JSON.stringify(JSON.stringify(fixture('B')))+')');await task;
  assert.equal(a.calls.length,1);assert.equal(a.run('snapshot'),null);
});
