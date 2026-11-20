// Peoplecare claims bridge (host side). Same queue pattern as the Woolworths bridge: the `health-claims` skill drops
// a JSON request in QUEUE/in and reads the answer from QUEUE/out. Chrome stays signed in on the server (George signs
// in once, with MFA, through an ssh tunnel); agents never see the login. Claims live in the "claims" database on hp-db.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { makeDb } from './db.mjs';
import { makeBrowser } from './browser.mjs';
import { makeOps, validate } from './ops.mjs';

const HOME = process.env.HOME;
const DATA = process.env.CLAIMS_DATA || path.join(HOME, 'projects/.nanoclaw-data/claims');
const QUEUE = path.join(DATA, 'queue');
const FILES = path.join(DATA, 'files');
const log = (...a) => console.log(new Date().toISOString(), ...a);

for (const d of [QUEUE, path.join(QUEUE, 'in'), path.join(QUEUE, 'out'), FILES]) { fs.mkdirSync(d, { recursive: true }); fs.chmodSync(d, 0o777); }
fs.chmodSync(DATA, 0o755);

const db = makeDb();
await db.migrate(path.join(path.dirname(fileURLToPath(import.meta.url)), 'schema.sql'));
const browser = makeBrowser();
const ops = makeOps({ db, browser, filesDir: FILES });

let busy = false;
async function handle(req) {
  const bad = validate(req);
  if (bad) return { ok: false, error: bad };
  try { return { ok: true, data: await ops[req.op](req) }; } catch (e) { return { ok: false, error: String(e.message || e).slice(0, 300) }; }
}
async function sweep() {
  if (busy) return;
  busy = true;
  try {
    for (const f of fs.readdirSync(path.join(QUEUE, 'in')).sort()) {
      if (f.endsWith('.tmp')) continue;
      if (!/^[a-z0-9-]{1,60}\.json$/.test(f)) { fs.rmSync(path.join(QUEUE, 'in', f), { force: true }); continue; }
      const file = path.join(QUEUE, 'in', f);
      let req; try { req = JSON.parse(fs.readFileSync(file, 'utf8')); } catch { req = null; }
      fs.rmSync(file, { force: true });
      const res = req ? await handle(req) : { ok: false, error: 'unreadable request' };
      log(req?.op, res.ok ? 'ok' : 'FAILED ' + res.error);
      const out = path.join(QUEUE, 'out', f);
      fs.writeFileSync(out + '.tmp', JSON.stringify(res)); fs.chmodSync(out + '.tmp', 0o666); fs.renameSync(out + '.tmp', out);
    }
    for (const f of fs.readdirSync(path.join(QUEUE, 'out'))) {
      const p = path.join(QUEUE, 'out', f);
      if (Date.now() - fs.statSync(p).mtimeMs > 10 * 60_000) fs.rmSync(p, { force: true });
    }
  } catch (e) { log('sweep error', e.message); } finally { busy = false; }
}

// Renew the Peoplecare session every 10 minutes (its token lasts 30) and note when it is lost.
let wasIn = null;
setInterval(async () => {
  if (busy) return;
  try {
    const s = await browser.keepAlive();
    const now = s.signed_in !== false;
    if (now !== wasIn) { log('session', now ? 'signed in' : 'SIGNED OUT: George must sign in again'); wasIn = now; }
  } catch (e) { if (wasIn !== false) log('session check failed:', e.message); wasIn = false; }
}, 10 * 60_000);

log('claims bridge up; queue', QUEUE);
setInterval(sweep, 700);
