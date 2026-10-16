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
      return {ok: true, json: async () => value};
    },
    Blob, URL: {createObjectURL: () => 'blob:synthetic', revokeObjectURL() {}},
    setTimeout: callback => callback(), console,
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
