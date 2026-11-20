// Runs the claim rules against a scratch Postgres database (claims_test on hp-db) with a fake browser.
// Skipped when Docker/hp-db is not available. Run: node --test ops.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { makeDb } from './db.mjs';
import { makeOps, normProvider, normName, validate } from './ops.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
let up = true;
try { execFileSync('docker', ['exec', 'hp-db', 'psql', '-U', 'claims', '-d', 'claims_test', '-c', 'select 1'], { stdio: 'ignore' }); } catch { up = false; }

test('provider names are normalised', () => {
  assert.equal(normProvider('Example Physio (via Cliniko)'), 'example physio');
  assert.equal(normProvider('EXAMPLE  Physio Pty Ltd'), 'example physio');
  assert.equal(normName('Mr Alex Example'), 'alex example');
});
test('validation rejects malformed requests', () => {
  assert.match(validate({ op: 'claim.add' }), /needs/);
  assert.match(validate({ op: 'nope' }), /unknown/);
  assert.match(validate({ op: 'claim.add', provider: 'a', patient: 'b', invoice_no: '1', pdf: '/x', reference: 'r', date: '20/11/2026' }), /YYYY/);
  assert.equal(validate({ op: 'claim.submit', id: 1, code: '1234' }), null);
});

test('claim lifecycle, allowlist, duplicates and approval', { skip: !up && 'hp-db not available' }, async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'claims-test-'));
  const pdf = (name, extra = '') => { fs.writeFileSync(path.join(dir, name), '%PDF-1.4\n' + 'x'.repeat(300) + extra); return name; };
  const db = makeDb({ database: 'claims_test' });
  await db.q('DROP SCHEMA public CASCADE; CREATE SCHEMA public;');
  await db.migrate(path.join(here, 'schema.sql'));
  await db.q("INSERT INTO patients VALUES ('alex example', 'Alex Example')");
  const calls = [];
  const browser = {
    session: async () => ({ signed_in: true }),
    prepare: async (a) => { calls.push(['prepare', a]); return { reference: a.reference }; },
    submit: async (a) => { calls.push(['submit', a]); return 'Claim_123'; },
    leave: async () => calls.push(['leave']),
  };
  const ops = makeOps({ db, browser, filesDir: dir, rand: () => '4821' });
  const add = (o = {}) => ops['claim.add']({ provider: 'Example Physio', patient: 'Mr Alex Example', invoice_no: '1001', date: '2026-11-20', amount: 90, service: 'Chiropractic', reference: 'physio', pdf: pdf('a.pdf'), ...o });

  // unknown provider: held, cannot be prepared
  let c = await add();
  assert.equal(c.status, 'pending_provider'); assert.equal(c.patient_known, true); assert.equal(c.amount, 90);
  await assert.rejects(ops['claim.prepare']({ id: c.id }), /not on the allowed list/);
  assert.equal(calls.length, 0);

  // duplicate by invoice number and by file contents
  assert.equal((await add({ pdf: pdf('b.pdf', 'different bytes') })).duplicate, true);
  assert.equal((await add({ invoice_no: '999', pdf: pdf('c.pdf') })).duplicate, true);

  // adding the provider releases the held claim
  const r = await ops['allow.add']({ name: 'example physio pty ltd' });
  assert.deepEqual(r.now_ready, [c.id]);
  assert.equal((await ops['allow.list']()).length, 1);

  // prepare gives a code; submit needs it exactly
  const p = await ops['claim.prepare']({ id: c.id });
  assert.equal(p.approval_code, '4821'); assert.equal(p.status, 'prepared');
  assert.deepEqual(calls[0][1].files, [fs.realpathSync(path.join(dir, 'a.pdf'))]);
  await assert.rejects(ops['claim.submit']({ id: c.id, code: '0000' }), /wrong/);
  assert.equal(calls.filter((x) => x[0] === 'submit').length, 0);
  const s = await ops['claim.submit']({ id: c.id, code: '4821' });
  assert.equal(s.status, 'submitted'); assert.equal(s.peoplecare_ref, 'Claim_123');
  await assert.rejects(ops['claim.submit']({ id: c.id, code: '4821' }), /not prepared/);
  await assert.rejects(ops['claim.cancel']({ id: c.id }), /already submitted/);

  // removing the provider sends later claims back to approval; history is kept
  await ops['allow.remove']({ name: 'Example Physio' });
  assert.equal((await ops['allow.list']()).length, 0);
  const c2 = await add({ invoice_no: '2', pdf: pdf('d.pdf', 'more') });
  assert.equal(c2.status, 'pending_provider');
  await assert.rejects(ops['allow.remove']({ name: 'Example Physio' }), /not on the allowed list/);

  // unknown patient is flagged, not blocked
  const c3 = await add({ invoice_no: '3', patient: 'Bob Smith', pdf: pdf('e.pdf', 'again') });
  assert.equal(c3.patient_known, false);

  // a failed prepare is recorded and can be retried
  await ops['allow.add']({ name: 'Example Physio' });
  browser.prepare = async () => { throw new Error('the PDF did not attach'); };
  await assert.rejects(ops['claim.prepare']({ id: c2.id }), /did not attach/);
  assert.equal((await ops['claim.show']({ id: c2.id })).status, 'failed');
  browser.prepare = async (a) => ({ reference: a.reference });
  assert.equal((await ops['claim.prepare']({ id: c2.id })).status, 'prepared');
  assert.equal((await ops['claim.cancel']({ id: c2.id })).status, 'cancelled');
  assert.ok((await ops['claim.list']({ status: 'cancelled' })).length === 1);
});

test('only PDFs inside the claims folder can be uploaded', { skip: !up && 'hp-db not available' }, async () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'claims-test-'));
  const outside = fs.mkdtempSync(path.join(os.tmpdir(), 'claims-out-'));
  fs.writeFileSync(path.join(outside, 'x.pdf'), '%PDF-1.4\n' + 'x'.repeat(300));
  fs.writeFileSync(path.join(dir, 'fake.pdf'), 'not a pdf '.repeat(40));
  fs.symlinkSync(path.join(outside, 'x.pdf'), path.join(dir, 'link.pdf'));
  const ops = makeOps({ db: makeDb({ database: 'claims_test' }), browser: {}, filesDir: dir });
  const base = { provider: 'P', patient: 'Q', invoice_no: 'z1', reference: 'r' };
  await assert.rejects(ops['claim.add']({ ...base, pdf: path.join(outside, 'x.pdf') }), /plain file name/);
  await assert.rejects(ops['claim.add']({ ...base, pdf: '../x.pdf' }), /plain file name/);
  await assert.rejects(ops['claim.add']({ ...base, pdf: 'link.pdf' }), /must be saved in/);
  await assert.rejects(ops['claim.add']({ ...base, pdf: 'fake.pdf' }), /not a PDF/);
  await assert.rejects(ops['claim.add']({ ...base, pdf: 'missing.pdf' }), /does not exist/);
});

import { recoverTab } from './recover.mjs';

function recoverDeps({ liveAfterReplace, liveAfterRestart, canRestart = true }) {
  const calls = [];
  let state = 'frozen';
  const fetchFn = async (url, opts) => {
    calls.push(opts?.method === 'PUT' ? 'new:' + url.split('/json/new?')[1] : url.includes('/close/') ? 'close' : 'list');
    if (opts?.method === 'PUT' && liveAfterReplace) state = 'live';
    return { json: async () => [{ id: 'A', type: 'page', url: 'https://oms.peoplecare.com.au/home' }] };
  };
  return {
    calls,
    deps: {
      cdp: 'http://x', site: 'oms.peoplecare.com.au', fetchFn, sleep: async () => {}, canRestart: () => canRestart,
      tryTabs: async () => (state === 'live' ? 'conn' : null),
      restartChrome: async () => { calls.push('restart'); if (liveAfterRestart) state = 'live'; },
    },
  };
}

test('recoverTab replaces a frozen tab on Home without restarting Chrome when that is enough', async () => {
  const { deps, calls } = recoverDeps({ liveAfterReplace: true });
  assert.equal(await recoverTab(deps), 'conn');
  assert.deepEqual(calls, ['list', 'close', 'new:https://oms.peoplecare.com.au/']);
});

test('recoverTab restarts Chrome when a replacement tab is frozen too', async () => {
  const { deps, calls } = recoverDeps({ liveAfterRestart: true });
  assert.equal(await recoverTab(deps), 'conn');
  assert.ok(calls.includes('restart'));
});

test('recoverTab does not restart Chrome again within the cool-down, and fails if nothing helps', async () => {
  const a = recoverDeps({ canRestart: false });
  await assert.rejects(recoverTab(a.deps), /restarted recently/);
  assert.ok(!a.calls.includes('restart'));
  await assert.rejects(recoverTab(recoverDeps({}).deps), /did not bring it back/);
});
