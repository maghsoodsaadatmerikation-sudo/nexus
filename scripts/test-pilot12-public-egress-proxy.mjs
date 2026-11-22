#!/usr/bin/env node
// Disposable, purely local regression for Pilot 12's CONNECT proxy.
// No public host is contacted, and this test cannot attest a deployed PWA.
import assert from 'node:assert/strict';
import net from 'node:net';
import {once} from 'node:events';
import {startProbeProxy} from './pilot12-public-egress-proxy.mjs';

function connect(port) {
  return new Promise((resolve, reject) => {
    const socket = net.connect({host:'127.0.0.1',port});
    const deadline = setTimeout(() => socket.destroy(Error('local-proxy-test-timeout')), 2000);
    socket.once('connect', () => {clearTimeout(deadline);resolve(socket);});
    socket.once('error', error => {clearTimeout(deadline);reject(error);});
  });
}
async function invalidConnect(port) {
  const socket = await connect(port);
  let reply = '';
  socket.on('data', chunk => {reply += chunk.toString('latin1');});
  const completed = once(socket, 'end');
  socket.write('CONNECT not-allowlisted.invalid:443 HTTP/1.1\r\nHost: not-allowlisted.invalid\r\n\r\n');
  await completed;
  socket.destroy();
  assert.match(reply, /^HTTP\/1\.1 403 Forbidden\r\n/);
}
async function assertRefused(port) {
  await assert.rejects(connect(port), error => error?.code === 'ECONNREFUSED');
}

const proxy = await startProbeProxy();
try {
  assert.equal(proxy.stats().listening, true);
  assert.equal(proxy.stats().live, true);
  assert.equal(proxy.stats().allowed, 0);
  await invalidConnect(proxy.port);
  assert.equal(proxy.stats().unexpected, 1);
  assert.equal(proxy.stats().blocked, 1);
  assert.equal(proxy.stats().allowed, 0);
  const hanging = await connect(proxy.port);
  const closed = once(hanging, 'close');
  assert.ok(proxy.stats().active >= 1);
  await proxy.cut();
  await closed;
  assert.deepEqual(
    {live:proxy.stats().live, listening:proxy.stats().listening, active:proxy.stats().active},
    {live:false,listening:false,active:0}
  );
  await assertRefused(proxy.port);
  // Must not re-open on duplicate cut or cleanup.
  await proxy.cut();
  await proxy.close();
  await assertRefused(proxy.port);
  assert.equal(proxy.stats().allowed, 0);
  console.log(JSON.stringify({status:'PASS',checks:10,external_egress:0,
    listener_closed:true,tracked_sockets:0,authority:'none'}));
} finally {
  await proxy.close();
}
