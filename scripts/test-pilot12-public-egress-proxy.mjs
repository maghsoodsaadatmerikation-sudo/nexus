import assert from 'node:assert/strict';
import {once} from 'node:events';
import net from 'node:net';
import test from 'node:test';
import {startProbeProxy} from './pilot12-public-egress-proxy.mjs';

const dial=net.createConnection;
const connectLine='CONNECT nexus-offline-pilot.onrender.com:443 HTTP/1.1\r\n\r\n';
async function clientFor(proxy) {
  const socket=dial({host:'127.0.0.1',port:proxy.port});
  socket.on('error',()=>{});
  await once(socket,'connect');
  return socket;
}
async function closed(socket) {
  if(socket.closed)return;
  await new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>reject(Error('socket-close-timeout')),2000);
    socket.once('close',()=>{clearTimeout(timer);resolve()});
  });
}

test('cut rejects new complete, partial and idle sockets before any dial',async t=>{
  let dials=0;
  t.mock.method(net,'connect',()=>{dials++;throw Error('forbidden external dial')});
  const proxy=await startProbeProxy();
  try {
    await proxy.cut();
    for(const bytes of [connectLine,'CONNECT ','', 'CONNECT other.invalid:443 HTTP/1.1\r\n\r\n']) {
      const socket=await clientFor(proxy);
      if(bytes)socket.write(bytes);
      await closed(socket);
      assert.equal(proxy.stats().active,0);
      assert.equal(proxy.stats().allowed,0);
      assert.equal(proxy.stats().live,false);
    }
    assert.equal(dials,0);
    assert.equal(proxy.stats().blocked,4);
  } finally {await proxy.close()}
});

test('online allowlist still rejects unrelated hosts without an external dial',async t=>{
  let dials=0;
  t.mock.method(net,'connect',()=>{dials++;throw Error('forbidden external dial')});
  const proxy=await startProbeProxy();
  let socket;
  try {
    socket=await clientFor(proxy);
    const response=once(socket,'data');
    socket.write('CONNECT other.invalid:443 HTTP/1.1\r\n\r\n');
    assert.match((await response)[0].toString(),/^HTTP\/1.1 403 /);
    assert.equal(dials,0);
    assert.equal(proxy.stats().unexpected,1);
  } finally {socket?.destroy();await proxy.close()}
});

test('cut closes a real established tunnel and never admits a replacement',async t=>{
  const echo=net.createServer(socket=>{socket.on('error',()=>{});socket.pipe(socket)});
  await new Promise(resolve=>echo.listen(0,'127.0.0.1',resolve));
  let dials=0;
  t.mock.method(net,'connect',options=>{
    assert.deepEqual(options,{host:'nexus-offline-pilot.onrender.com',port:443});
    dials++;
    return dial({host:'127.0.0.1',port:echo.address().port});
  });
  const proxy=await startProbeProxy();
  let socket;
  try {
    socket=await clientFor(proxy);
    let response=once(socket,'data');
    socket.write(connectLine);
    assert.match((await response)[0].toString(),/^HTTP\/1.1 200 /);
    response=once(socket,'data');
    socket.write('synthetic tunnel payload');
    assert.equal((await response)[0].toString(),'synthetic tunnel payload');
    assert.equal(proxy.stats().allowed,1);
    assert.equal(dials,1);
    await proxy.cut();
    await closed(socket);
    for(let i=0;i<8;i++) {
      const replacement=await clientFor(proxy);
      replacement.write(connectLine);
      await closed(replacement);
    }
    assert.deepEqual(proxy.stats(),{allowed:1,blocked:8,unexpected:0,active:0,live:false});
    assert.equal(dials,1);
  } finally {
    socket?.destroy();
    await proxy.close();
    await new Promise(resolve=>echo.close(resolve));
  }
});
