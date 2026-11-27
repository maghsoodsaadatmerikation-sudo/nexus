// Pilot 12: disposable test-only HTTPS CONNECT proxy.
//
// Public-origin Chromium uses this proxy for ALL outside-origin requests.
// Once a reviewed service worker is installed, cutting all tunnels and
// refusing new CONNECT requests prevents its network-first fetch from
// reaching the actual host. This is not deployed or used by NEXUS users.
import net from 'node:net';

const HOST = 'nexus-offline-pilot.onrender.com';
const LIMIT = 8192;
const CRLF = '\r\n\r\n';

export async function startProbeProxy() {
  let live = true;
  let allowed = 0;
  let blocked = 0;
  let unexpected = 0;
  const sockets = new Set();
  const closeSocket = socket => {
    sockets.delete(socket);
    socket.destroy();
  };
  const server = net.createServer(client => {
    client.on('error', () => closeSocket(client));
    // Chrome can open replacement proxy sockets after its tunnels are cut.
    // Refuse them at admission: a pending inbound CONNECT is not restored
    // external egress, and must not enter the active tunnel accounting.
    if(!live) {
      blocked++;
      client.destroy();
      return;
    }
    sockets.add(client);
    let buf = Buffer.alloc(0);
    let accepted = false;
    let upstream = null;
    const reject = status => {
      blocked++;
      client.end('HTTP/1.1 ' + status +
        '\r\nContent-Length: 0\r\nConnection: close\r\n\r\n');
    };
    const onFirstData = chunk => {
      if(accepted) return;
      buf = Buffer.concat([buf, chunk]);
      if(buf.length > LIMIT) {
        unexpected++;
        reject('431 Request Header Fields Too Large');
        return;
      }
      const end = buf.indexOf(CRLF);
      if(end === -1) return;
      const line = buf.subarray(0, end).toString('latin1').split('\r\n')[0];
      const expected = 'CONNECT ' + HOST + ':443 HTTP/1.1';
      if(line !== expected) {
        unexpected++;
        reject('403 Forbidden');
        return;
      }
      accepted = true;
      client.removeListener('data', onFirstData);
      if(!live) {
        reject('503 Service Unavailable');
        return;
      }
      upstream = net.connect({host:HOST, port:443});
      sockets.add(upstream);
      upstream.on('close', () => sockets.delete(upstream));
      upstream.on('error', () => closeSocket(client));
      upstream.once('connect', () => {
        if(!live) {
          closeSocket(upstream);
          reject('503 Service Unavailable');
          return;
        }
        allowed++;
        client.write('HTTP/1.1 200 Connection Established\r\n\r\n');
        const remainder = buf.subarray(end + CRLF.length);
        if(remainder.length) upstream.write(remainder);
        client.pipe(upstream);
        upstream.pipe(client);
      });
    };
    client.on('data', onFirstData);
    client.on('close', () => {
      sockets.delete(client);
      if(upstream) closeSocket(upstream);
    });
  });
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });
  const addr = server.address();
  if(!addr || typeof addr === 'string' || !addr.port)
    throw Error('disposable-proxy-no-local-port');
  return {
    port: addr.port,
    stats: () => ({allowed, blocked, unexpected, active:sockets.size, live}),
    cut: async () => {
      live = false;
      for(const socket of [...sockets]) closeSocket(socket);
      await new Promise(resolve => setTimeout(resolve, 150));
      if(sockets.size !== 0) throw Error('proxy-tunnels-not-closed');
    },
    close: async () => {
      live = false;
      for(const socket of [...sockets]) closeSocket(socket);
      await new Promise(resolve => server.close(resolve));
    }
  };
}
