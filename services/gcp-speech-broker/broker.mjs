// Google Speech-to-Text v2 token broker. Speech v2 (Chirp models) rejects API keys and wants an OAuth token,
// which the OneCLI vault cannot mint. The vault holds the service-account JSON (base64) and injects it into
// requests to this broker as the X-SA-Key header; the broker signs a short-lived token with it, forwards the
// request to Google and returns the answer. The key lives only in the vault and, per request, in memory:
// never on disk, never logged. Only Speech v2 `recognize` calls are forwarded. No dependencies (Node 22).
import crypto from 'node:crypto';

const TOKEN_URL = 'https://oauth2.googleapis.com/token'; // fixed: never taken from the key file (no SSRF via a tampered key)
const SCOPE = 'https://www.googleapis.com/auth/cloud-platform';
const ROUTE = /^\/gcp-speech\/(v2\/projects\/[a-z][a-z0-9-]{4,60}\/locations\/([a-z0-9-]{1,40})\/recognizers\/_:recognize)$/;
export const MAX_BODY = 12 * 1024 * 1024;

/** Decode and sanity-check the vault value (base64 of the service-account JSON). */
export function parseKey(b64) {
  let k;
  try { k = JSON.parse(Buffer.from(String(b64), 'base64').toString('utf8')); } catch { throw new Error('X-SA-Key is not base64 JSON'); }
  if (k.type !== 'service_account' || typeof k.private_key !== 'string' || typeof k.client_email !== 'string') throw new Error('X-SA-Key is not a service-account key');
  if (!k.client_email.endsWith('.iam.gserviceaccount.com')) throw new Error('unexpected service-account email');
  return { email: k.client_email, privateKey: k.private_key, keyId: k.private_key_id };
}

const b64url = (b) => Buffer.from(b).toString('base64url');

export function signJwt(key, now = Date.now()) {
  const iat = Math.floor(now / 1000);
  const head = b64url(JSON.stringify({ alg: 'RS256', typ: 'JWT', ...(key.keyId ? { kid: key.keyId } : {}) }));
  const claims = b64url(JSON.stringify({ iss: key.email, scope: SCOPE, aud: TOKEN_URL, iat, exp: iat + 3600 }));
  const sig = crypto.sign('RSA-SHA256', Buffer.from(`${head}.${claims}`), key.privateKey);
  return `${head}.${claims}.${b64url(sig)}`;
}

/** Which Google host serves a location: `global` is the plain host, others are `<location>-speech.googleapis.com`. */
export function hostFor(location) {
  return location === 'global' ? 'speech.googleapis.com' : `${location}-speech.googleapis.com`;
}

export function makeBroker({ fetchFn = fetch, now = () => Date.now(), log = () => {} } = {}) {
  const tokens = new Map(); // sha256(header value) -> { token, exp }; the key itself is not kept

  async function tokenFor(b64) {
    const id = crypto.createHash('sha256').update(b64).digest('hex');
    const hit = tokens.get(id);
    if (hit && hit.exp - 120_000 > now()) return hit.token;
    const key = parseKey(b64);
    const r = await fetchFn(TOKEN_URL, {
      method: 'POST',
      headers: { 'content-type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer', assertion: signJwt(key, now()) }),
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok || !d.access_token) throw new Error(`Google token request failed (${r.status}${d.error ? ' ' + d.error : ''})`);
    tokens.set(id, { token: d.access_token, exp: now() + (d.expires_in || 3600) * 1000 });
    return d.access_token;
  }

  /** Returns { status, body, type } for one incoming request. */
  async function handle({ method, url, headers, body }) {
    const m = ROUTE.exec(String(url).split('?')[0]);
    if (!m) return { status: 404, body: JSON.stringify({ error: 'not found' }) };
    if (method !== 'POST') return { status: 405, body: JSON.stringify({ error: 'POST only' }) };
    const b64 = headers['x-sa-key'];
    if (!b64) return { status: 401, body: JSON.stringify({ error: 'missing X-SA-Key (the vault injects it)' }) };
    let token;
    try { token = await tokenFor(b64); } catch (e) { log('token error:', e.message); return { status: 502, body: JSON.stringify({ error: e.message }) }; }
    const t0 = now();
    const r = await fetchFn(`https://${hostFor(m[2])}/${m[1]}`, {
      method: 'POST',
      headers: { authorization: `Bearer ${token}`, 'content-type': 'application/json' },
      body,
    });
    const text = await r.text();
    log(`recognize ${m[2]} -> ${r.status} in ${now() - t0} ms`);
    return { status: r.status, body: text };
  }
  return { handle, tokenFor };
}
