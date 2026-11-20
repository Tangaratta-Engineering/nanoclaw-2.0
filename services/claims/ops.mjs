// Claim operations: allowlist, duplicate checks, the approval step, and the calls into the browser driver.
// `db` and `browser` are injected so the rules can be tested without Postgres or Chrome.
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

const MAX_PDF = 10 * 1024 * 1024;

/** "Example Physio (via Cliniko) Pty Ltd" -> "example physio". */
export function normProvider(name) {
  return String(name || '').toLowerCase().replace(/\([^)]*\)/g, ' ').replace(/\b(pty|ltd|limited|p\/l)\b/g, ' ')
    .replace(/[^a-z0-9]+/g, ' ').trim();
}
export const normName = (n) => String(n || '').toLowerCase().replace(/\b(mr|mrs|ms|miss|dr|master)\b/g, ' ').replace(/[^a-z]+/g, ' ').trim();

const str = (v, max = 200) => typeof v === 'string' && v.trim() && v.length <= max;

export function validate(req) {
  if (!req || typeof req !== 'object' || typeof req.op !== 'string') return 'bad request';
  switch (req.op) {
    case 'status': case 'claim.list': case 'allow.list': return null;
    case 'claim.show': case 'claim.prepare': case 'claim.cancel': return Number.isInteger(req.id) ? null : 'id must be a whole number';
    case 'claim.submit': return Number.isInteger(req.id) && str(req.code, 8) ? null : 'needs id and code';
    case 'allow.add': case 'allow.remove': return str(req.name, 120) ? null : 'needs a provider name';
    case 'claim.add':
      if (!str(req.provider, 120) || !str(req.patient, 120) || !str(req.invoice_no, 60) || !str(req.pdf, 120) || !str(req.reference, 80)) return 'claim.add needs provider, patient, invoice_no, pdf and reference';
      if (req.amount != null && !(typeof req.amount === 'number' && req.amount >= 0 && req.amount < 100000)) return 'amount must be dollars as a number';
      if (req.date != null && !/^\d{4}-\d{2}-\d{2}$/.test(req.date)) return 'date must be YYYY-MM-DD';
      return null;
    default: return `unknown op ${req.op}`;
  }
}

export function makeOps({ db, browser, filesDir, rand = () => String(crypto.randomInt(1000, 10000)) }) {
  const FILES = fs.existsSync(filesDir) ? fs.realpathSync(filesDir) : path.resolve(filesDir);
  const log = (claim_id, event, detail = '') => db.q(`INSERT INTO claim_log (claim_id, event, detail) VALUES (((:'j')::jsonb->>'c')::int, (:'j')::jsonb->>'e', (:'j')::jsonb->>'d')`, { c: claim_id, e: event, d: String(detail).slice(0, 300) });
  const getClaim = async (id) => {
    const c = await db.q(`SELECT row_to_json(c) FROM claims c WHERE id = ((:'j')::jsonb->>'id')::int`, { id });
    if (!c) throw new Error(`no claim ${id}`);
    return c;
  };
  const view = (c) => ({ id: c.id, status: c.status, provider: c.provider_name, patient: c.patient_name, patient_known: c.patient_known,
    invoice_no: c.invoice_no, date: c.invoice_date, amount: c.amount_cents == null ? null : c.amount_cents / 100, reference: c.reference,
    peoplecare_ref: c.peoplecare_ref, error: c.error });

  /** Only files inside the claims folder may ever be uploaded to Peoplecare. */
  function safePdf(name) {
    if (!/^[A-Za-z0-9._-]{1,120}$/.test(name) || name.startsWith('.')) throw new Error('the PDF must be given as a plain file name inside the claims folder');
    let real;
    try { real = fs.realpathSync(path.join(FILES, name)); } catch { throw new Error('that PDF file does not exist'); }
    if (!real.startsWith(FILES + path.sep)) throw new Error(`the PDF must be saved in ${FILES}`);
    const st = fs.statSync(real);
    if (!st.isFile() || st.size > MAX_PDF || st.size < 100) throw new Error('the PDF is empty or over 10 MB');
    const buf = fs.readFileSync(real);
    if (buf.subarray(0, 5).toString() !== '%PDF-') throw new Error('that file is not a PDF');
    return { real, sha: crypto.createHash('sha256').update(buf).digest('hex') };
  }

  const ops = {
    async status() { return browser.session(); },

    async 'allow.list'() {
      return db.q(`SELECT coalesce(json_agg(t ORDER BY name), '[]') FROM (SELECT display_name AS name, added_at, removed_at FROM allowed_providers WHERE removed_at IS NULL) t`);
    },
    async 'allow.add'(req) {
      const key = normProvider(req.name);
      if (!key) throw new Error('that provider name has no usable letters');
      await db.q(`INSERT INTO allowed_providers (provider_key, display_name, note) VALUES ((:'j')::jsonb->>'k', (:'j')::jsonb->>'n', (:'j')::jsonb->>'note')
        ON CONFLICT (provider_key) DO UPDATE SET removed_at = NULL, added_at = now(), display_name = EXCLUDED.display_name`, { k: key, n: req.name.trim(), note: req.note || null });
      const ids = await db.q(`WITH u AS (UPDATE claims SET status='ready' WHERE provider_key=(:'j')::jsonb->>'k' AND status='pending_provider' RETURNING id) SELECT coalesce(json_agg(id),'[]') FROM u`, { k: key });
      return { provider: req.name.trim(), now_ready: ids };
    },
    async 'allow.remove'(req) {
      const key = normProvider(req.name);
      const n = await db.q(`WITH u AS (UPDATE allowed_providers SET removed_at = now() WHERE provider_key=(:'j')::jsonb->>'k' AND removed_at IS NULL RETURNING 1) SELECT count(*) FROM u`, { k: key });
      if (!n) throw new Error(`"${req.name}" is not on the allowed list`);
      // claims already waiting on that provider fall back to needing approval
      await db.q(`UPDATE claims SET status='pending_provider' WHERE provider_key=(:'j')::jsonb->>'k' AND status IN ('ready')`, { k: key });
      return { removed: req.name.trim() };
    },

    async 'claim.add'(req) {
      const { real, sha } = safePdf(req.pdf);
      const key = normProvider(req.provider);
      const dup = await db.q(`SELECT row_to_json(c) FROM claims c WHERE pdf_sha256 = (:'j')::jsonb->>'s' OR (provider_key = (:'j')::jsonb->>'k' AND invoice_no = (:'j')::jsonb->>'i') LIMIT 1`, { s: sha, k: key, i: req.invoice_no });
      if (dup) return { duplicate: true, ...view(dup) };
      const allowed = await db.q(`SELECT count(*) FROM allowed_providers WHERE provider_key=(:'j')::jsonb->>'k' AND removed_at IS NULL`, { k: key });
      const known = await db.q(`SELECT count(*) FROM patients WHERE name_key = (:'j')::jsonb->>'p'`, { p: normName(req.patient) });
      const c = await db.q(`INSERT INTO claims (provider_key, provider_name, patient_name, patient_known, invoice_no, invoice_date, amount_cents, service, reference, email_id, pdf_path, pdf_sha256, status)
        VALUES ((:'j')::jsonb->>'k', (:'j')::jsonb->>'prov', (:'j')::jsonb->>'pat', ((:'j')::jsonb->>'known')::boolean, (:'j')::jsonb->>'i',
                NULLIF((:'j')::jsonb->>'d','')::date, NULLIF((:'j')::jsonb->>'a','')::int, (:'j')::jsonb->>'svc', (:'j')::jsonb->>'ref', (:'j')::jsonb->>'em',
                (:'j')::jsonb->>'path', (:'j')::jsonb->>'s', (:'j')::jsonb->>'st') RETURNING row_to_json(claims)`,
      { k: key, prov: req.provider.trim(), pat: req.patient.trim(), known: Number(known) > 0, i: req.invoice_no.trim(), d: req.date || '',
        a: req.amount == null ? '' : String(Math.round(req.amount * 100)), svc: req.service || '', ref: req.reference.trim(), em: req.email_id || '',
        path: real, s: sha, st: Number(allowed) > 0 ? 'ready' : 'pending_provider' });
      await log(c.id, 'added', c.status);
      return { duplicate: false, ...view(c), needs_provider_approval: c.status === 'pending_provider' };
    },
    async 'claim.list'(req) {
      return db.q(`SELECT coalesce(json_agg(t), '[]') FROM (SELECT id, status, provider_name AS provider, patient_name AS patient, invoice_no, invoice_date AS date, amount_cents/100.0 AS amount, peoplecare_ref
        FROM claims WHERE ((:'j')::jsonb->>'s') IS NULL OR status = (:'j')::jsonb->>'s' ORDER BY id DESC LIMIT 50) t`, { s: req.status || null });
    },
    async 'claim.show'(req) { return view(await getClaim(req.id)); },

    async 'claim.prepare'(req) {
      const c = await getClaim(req.id);
      if (c.status === 'pending_provider') throw new Error(`"${c.provider_name}" is not on the allowed list yet: ask George to approve the provider first`);
      if (!['ready', 'prepared', 'failed'].includes(c.status)) throw new Error(`claim ${c.id} is ${c.status}`);
      const { real } = safePdf(path.basename(c.pdf_path));
      let summary;
      try { summary = await browser.prepare({ files: [real], reference: c.reference }); }
      catch (e) { await db.q(`UPDATE claims SET status='failed', error=(:'j')::jsonb->>'e' WHERE id=((:'j')::jsonb->>'id')::int`, { id: c.id, e: e.message.slice(0, 250) }); await log(c.id, 'prepare failed', e.message); throw e; }
      const code = rand();
      await db.q(`UPDATE claims SET status='prepared', approval_code=(:'j')::jsonb->>'c', prepared_at=now(), error=NULL WHERE id=((:'j')::jsonb->>'id')::int`, { id: c.id, c: code });
      await log(c.id, 'prepared');
      return { ...view({ ...c, status: 'prepared' }), approval_code: code, review_page: summary };
    },
    async 'claim.submit'(req) {
      const c = await getClaim(req.id);
      if (c.status !== 'prepared') throw new Error(`claim ${c.id} is ${c.status}, not prepared: prepare it first`);
      if (String(req.code).trim() !== c.approval_code) throw new Error('that approval code is wrong: George must send the code shown on the card');
      let ref;
      try { ref = await browser.submit({ reference: c.reference, files: 1 }); }
      catch (e) { await db.q(`UPDATE claims SET status='failed', error=(:'j')::jsonb->>'e' WHERE id=((:'j')::jsonb->>'id')::int`, { id: c.id, e: e.message.slice(0, 250) }); await log(c.id, 'submit failed', e.message); throw e; }
      await db.q(`UPDATE claims SET status='submitted', submitted_at=now(), peoplecare_ref=(:'j')::jsonb->>'r', approval_code=NULL WHERE id=((:'j')::jsonb->>'id')::int`, { id: c.id, r: ref });
      await log(c.id, 'submitted', ref);
      return { ...view({ ...c, status: 'submitted', peoplecare_ref: ref }) };
    },
    async 'claim.cancel'(req) {
      const c = await getClaim(req.id);
      if (c.status === 'submitted') throw new Error('already submitted: it cannot be cancelled here');
      await db.q(`UPDATE claims SET status='cancelled', approval_code=NULL WHERE id=((:'j')::jsonb->>'id')::int`, { id: c.id });
      await log(c.id, 'cancelled');
      try { await browser.leave(); } catch { /* the page may already be gone */ }
      return view({ ...c, status: 'cancelled' });
    },
  };
  return ops;
}
