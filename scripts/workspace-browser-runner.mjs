#!/usr/bin/env node
// Drive only the browser process/profile started here, never an existing session.
import {spawn} from 'node:child_process';
import {mkdir, readFile} from 'node:fs/promises';
import path from 'node:path';

const [browser, page, profile, dimensions] = process.argv.slice(2);
if (!browser || !page || !profile || !/^\d+,\d+$/.test(dimensions || '') ||
    typeof WebSocket === 'undefined') throw new Error('browser runner requires Node 22 and explicit private inputs');
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
// Refuse every pre-existing profile rather than attaching to a user's session.
await mkdir(profile, {mode: 0o700});
const child = spawn(browser, ['--headless', '--no-sandbox', '--disable-dev-shm-usage',
  '--disable-background-networking', '--disable-extensions', '--no-first-run',
  '--no-default-browser-check', '--hide-scrollbars', '--force-device-scale-factor=1',
  '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=0',
  '--user-data-dir=' + profile, '--window-size=' + dimensions, page],
  {stdio: ['ignore', 'ignore', 'pipe']});
const started = Date.now();
let stage = 'launch';
let launchError;
child.on('error', error => {launchError = error});
const exited = new Promise(resolve => child.once('close', resolve));
child.stderr.on('data', () => {}); // Chrome diagnostics are not acceptance evidence.
let socket;
let serial = 0;
const pending = new Map();
function rpc(method, params = {}) {
  const id = ++serial;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      pending.delete(id);
      reject(new Error('private browser command timed out'));
    }, 5000);
    pending.set(id, {
      resolve: value => {clearTimeout(timer); resolve(value)},
      reject: error => {clearTimeout(timer); reject(error)},
    });
    socket.send(JSON.stringify({id, method, params}));
  });
}
async function waitFor(action, milliseconds) {
  const until = Date.now() + milliseconds;
  while (Date.now() < until) {
    if (launchError || child.exitCode !== null || child.signalCode !== null)
      throw new Error('private browser process exited before witness completion');
    const result = await action();
    if (result) return result;
    await delay(20);
  }
  throw new Error('real browser witness timed out');
}
try {
  stage = 'devtools-port';
  const port = await waitFor(async () => {
    try {
      const value = (await readFile(path.join(profile, 'DevToolsActivePort'), 'utf8')).split('\n')[0];
      return /^\d+$/.test(value) ? value : null;
    } catch {return null}
  }, 10000);
  stage = 'page-target';
  const target = await waitFor(async () => {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/list`, {signal: AbortSignal.timeout(2000)});
      if (!response.ok) throw new Error('private browser target endpoint rejected observation');
      return (await response.json()).find(item => item.type === 'page' && item.url === page);
    } catch (error) {
      // DevToolsActivePort can appear before its HTTP target endpoint responds.
      // Retry only transient observation failures within the startup deadline.
      // Never retry page actions or turn a missing/failed report into a PASS.
      if (error.name === 'TimeoutError' || error instanceof TypeError) return null;
      throw error;
    }
  }, 15000);
  stage = 'debugger-address';
  const address = new URL(target.webSocketDebuggerUrl);
  if (address.hostname !== '127.0.0.1' || address.port !== port)
    throw new Error('unexpected private browser debugger address');
  stage = 'debugger-connect';
  socket = new WebSocket(address);
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('private browser connection timed out')), 5000);
    socket.addEventListener('open', () => {clearTimeout(timer); resolve()}, {once: true});
    socket.addEventListener('error', error => {clearTimeout(timer); reject(error)}, {once: true});
  });
  socket.addEventListener('message', event => {
    const message = JSON.parse(event.data);
    const request = pending.get(message.id);
    if (!request) return;
    pending.delete(message.id);
    if (message.error) request.reject(new Error(message.error.message));
    else request.resolve(message.result);
  });
  socket.addEventListener('close', () => {
    for (const request of pending.values()) request.reject(new Error('private browser connection closed'));
    pending.clear();
  });
  stage = 'completed-report';
  const report = await waitFor(async () => {
    const response = await rpc('Runtime.evaluate', {
      expression: "document.getElementById('nexus-browser-result')?.textContent || ''",
      returnByValue: true,
    });
    if (response.exceptionDetails) throw new Error('browser report evaluation failed');
    return response.result.value || null;
  }, 15000);
  process.stdout.write(report + '\n');
} catch (error) {
  // Fixed labels and process state only: never dump page content, URLs, stderr,
  // profile paths or exception messages into diagnostic evidence.
  process.stderr.write(JSON.stringify({event: 'browser-witness-failure', stage,
    elapsed_ms: Date.now() - started, process_exited: child.exitCode !== null || child.signalCode !== null,
    launch_failed: Boolean(launchError), authority: 'none', production_verified: false}) + '\n');
  throw error;
} finally {
  if (socket?.readyState === WebSocket.OPEN) {
    await Promise.race([rpc('Browser.close').catch(() => {}), delay(1000)]);
    socket.close();
  }
  if (child.pid !== undefined && child.exitCode === null && child.signalCode === null) child.kill('SIGTERM');
  await Promise.race([exited, delay(3000)]);
  if (child.exitCode === null && child.signalCode === null) {
    child.kill('SIGKILL');
    await exited;
  }
}
