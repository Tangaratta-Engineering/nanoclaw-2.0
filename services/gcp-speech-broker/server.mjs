// HTTP front for the Google Speech token broker (see broker.mjs). Listens on the OneCLI network address only (172.22.0.1: the gateway reaches it, and its secret is not shared with another bridge),
// like the other host bridges the OneCLI gateway reaches; requests without the vault-injected key are refused.
import http from 'node:http';
import { makeBroker, MAX_BODY } from './broker.mjs';

const HOST = process.env.GCP_BROKER_HOST || '172.22.0.1';
const PORT = Number(process.env.GCP_BROKER_PORT || '8774');
const log = (...a) => console.log(new Date().toISOString(), ...a);
const broker = makeBroker({ log });

http.createServer((req, res) => {
  const chunks = [];
  let size = 0;
  req.on('data', (c) => {
    size += c.length;
    if (size > MAX_BODY) { res.writeHead(413).end(); req.destroy(); return; }
    chunks.push(c);
  });
  req.on('end', async () => {
    if (res.writableEnded) return;
    try {
      const out = await broker.handle({ method: req.method, url: req.url, headers: req.headers, body: Buffer.concat(chunks) });
      res.writeHead(out.status, { 'content-type': 'application/json' }).end(out.body);
    } catch (e) {
      log('error:', e.message);
      res.writeHead(502, { 'content-type': 'application/json' }).end(JSON.stringify({ error: 'broker error' }));
    }
  });
}).listen(PORT, HOST, () => log(`gcp speech broker on ${HOST}:${PORT}`));
