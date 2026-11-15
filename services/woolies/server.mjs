// Woolworths bridge (host side). Agents can't reach the host's Chrome, so they drop a JSON request into
// QUEUE/in and read the answer from QUEUE/out (the `woolworths` container skill does this). This process
// runs each request inside George's already-signed-in Chrome (CDP on 127.0.0.1:9222) by calling Woolworths'
// own website APIs from the page, so it looks like normal browsing. Lists only: it never touches the
// trolley, checkout or payment. No dependencies (Node 22 has fetch + WebSocket).
import fs from 'node:fs';
import path from 'node:path';
import { ops, validate } from './ops.mjs';

const HOME = process.env.HOME;
const DATA = process.env.WOOLIES_DATA || path.join(HOME, 'projects/.nanoclaw-data/woolies');
const QUEUE = path.join(DATA, 'queue');
const CDP = process.env.WOOLIES_CDP || 'http://127.0.0.1:9222';
const MIN_GAP_MS = 350; // pause between site calls
const log = (...a) => console.log(new Date().toISOString(), ...a);

for (const d of ['in', 'out']) fs.mkdirSync(path.join(QUEUE, d), { recursive: true, mode: 0o777 });
fs.chmodSync(QUEUE, 0o777); fs.chmodSync(path.join(QUEUE, 'in'), 0o777); fs.chmodSync(path.join(QUEUE, 'out'), 0o777);

/** Evaluate `fn(arg)` in the Woolworths page and return its JSON result. */
/** A tab that answers a trivial request within a few seconds. A frozen tab never answers, so it is skipped. */
function alive(ws) {
  return new Promise((res) => {
    const onMsg = (e) => { if (JSON.parse(e.data).id === 99) { ws.removeEventListener('message', onMsg); res(true); } };
    ws.addEventListener('message', onMsg);
    ws.send(JSON.stringify({ id: 99, method: 'Runtime.evaluate', params: { expression: '1', returnByValue: true } }));
    setTimeout(() => { ws.removeEventListener('message', onMsg); res(false); }, 4000);
  });
}

/** Connect to the first Woolworths tab that is actually responding. */
async function openTab() {
  const targets = await (await fetch(`${CDP}/json`)).json();
  const pages = targets.filter((x) => x.type === 'page' && x.url.includes('woolworths.com.au'));
  if (!pages.length) throw new Error('no Woolworths tab is open in the server Chrome');
  for (const t of pages) {
    const ws = new WebSocket(t.webSocketDebuggerUrl);
    try {
      await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error('cannot reach the server Chrome')); });
      if (await alive(ws)) return ws;
      log('skipping a frozen Woolworths tab:', t.url.slice(0, 80));
    } catch { /* try the next tab */ }
    try { ws.close(); } catch { /* ignore */ }
  }
  throw new Error('every Woolworths tab in the server Chrome is frozen: close or reload them');
}

async function inPage(fn, arg) {
  const ws = await openTab();
  try {
    const expr = `(${fn.toString()})(${JSON.stringify(arg)})`;
    const result = await new Promise((res, rej) => {
      ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.id === 1) res(m.result); };
      ws.send(JSON.stringify({ id: 1, method: 'Runtime.evaluate', params: { expression: expr, awaitPromise: true, returnByValue: true } }));
      setTimeout(() => rej(new Error('timed out talking to Woolworths')), 45000);
    });
    if (result.exceptionDetails) throw new Error('page error: ' + (result.exceptionDetails.exception?.description || 'unknown').slice(0, 200));
    return result.result.value;
  } finally { ws.close(); }
}

let last = 0;
async function handle(req) {
  const bad = validate(req);
  if (bad) return { ok: false, error: bad };
  const wait = last + MIN_GAP_MS - Date.now();
  if (wait > 0) await new Promise((r) => setTimeout(r, wait));
  try {
    const data = await ops[req.op](req, inPage);
    return { ok: true, data };
  } catch (e) {
    return { ok: false, error: String(e.message || e).slice(0, 300) };
  } finally { last = Date.now(); }
}

let busy = false;
async function sweep() {
  if (busy) return;
  busy = true;
  try {
    for (const f of fs.readdirSync(path.join(QUEUE, 'in')).sort()) {
      if (f.endsWith('.tmp')) continue; // still being written
      if (!/^[a-z0-9-]{1,60}\.json$/.test(f)) { fs.rmSync(path.join(QUEUE, 'in', f), { force: true }); continue; }
      const file = path.join(QUEUE, 'in', f);
      let req; try { req = JSON.parse(fs.readFileSync(file, 'utf8')); } catch { req = null; }
      fs.rmSync(file, { force: true });
      const res = req ? await handle(req) : { ok: false, error: 'unreadable request' };
      log(req?.op, res.ok ? 'ok' : 'FAILED ' + res.error);
      const out = path.join(QUEUE, 'out', f);
      fs.writeFileSync(out + '.tmp', JSON.stringify(res)); fs.chmodSync(out + '.tmp', 0o666); fs.renameSync(out + '.tmp', out);
    }
    // drop answers nobody collected
    for (const f of fs.readdirSync(path.join(QUEUE, 'out'))) {
      const p = path.join(QUEUE, 'out', f);
      if (Date.now() - fs.statSync(p).mtimeMs > 10 * 60_000) fs.rmSync(p, { force: true });
    }
  } catch (e) { log('sweep error', e.message); } finally { busy = false; }
}

log('woolies bridge up; queue', QUEUE);
setInterval(sweep, 700);
