import test from 'node:test';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import { makeBroker, parseKey, signJwt, hostFor } from './broker.mjs';

const { privateKey, publicKey } = crypto.generateKeyPairSync('rsa', { modulusLength: 2048 });
const pem = privateKey.export({ type: 'pkcs8', format: 'pem' });
const sa = { type: 'service_account', private_key: pem, private_key_id: 'kid1', client_email: 'x@proj.iam.gserviceaccount.com' };
const b64 = Buffer.from(JSON.stringify(sa)).toString('base64');
const path = '/gcp-speech/v2/projects/my-proj-123456/locations/global/recognizers/_:recognize';

function fakes() {
  const calls = [];
  let t = 1_700_000_000_000;
  const fetchFn = async (url, opts) => {
    calls.push({ url: String(url), opts });
    if (String(url).startsWith('https://oauth2.googleapis.com/token')) return { ok: true, status: 200, json: async () => ({ access_token: 'tok' + calls.length, expires_in: 3600 }) };
    return { ok: true, status: 200, text: async () => '{"results":[]}' };
  };
  return { calls, fetchFn, now: () => t, advance: (ms) => { t += ms; } };
}

test('signJwt makes a verifiable RS256 token for the service account', () => {
  const jwt = signJwt(parseKey(b64), 1_700_000_000_000);
  const [h, c, s] = jwt.split('.');
  assert.ok(crypto.verify('RSA-SHA256', Buffer.from(`${h}.${c}`), publicKey, Buffer.from(s, 'base64url')));
  const claims = JSON.parse(Buffer.from(c, 'base64url'));
  assert.equal(claims.iss, sa.client_email);
  assert.equal(claims.aud, 'https://oauth2.googleapis.com/token');
  assert.equal(claims.exp - claims.iat, 3600);
});

test('parseKey rejects things that are not a service-account key', () => {
  assert.throws(() => parseKey('not base64 json'));
  assert.throws(() => parseKey(Buffer.from('{"type":"authorized_user"}').toString('base64')));
  assert.throws(() => parseKey(Buffer.from(JSON.stringify({ ...sa, client_email: 'a@evil.com' })).toString('base64')));
});

test('forwards recognize to the right Google host with a bearer token, and caches the token', async () => {
  const f = fakes();
  const b = makeBroker({ fetchFn: f.fetchFn, now: f.now });
  const r1 = await b.handle({ method: 'POST', url: path, headers: { 'x-sa-key': b64 }, body: Buffer.from('{}') });
  assert.equal(r1.status, 200);
  const sent = f.calls.find((c) => c.url.includes('recognizers'));
  assert.equal(sent.url, 'https://speech.googleapis.com/v2/projects/my-proj-123456/locations/global/recognizers/_:recognize');
  assert.equal(sent.opts.headers.authorization, 'Bearer tok1');
  await b.handle({ method: 'POST', url: path, headers: { 'x-sa-key': b64 }, body: Buffer.from('{}') });
  assert.equal(f.calls.filter((c) => c.url.includes('oauth2')).length, 1); // second call reused the token
  f.advance(3500_000); // past expiry minus margin
  await b.handle({ method: 'POST', url: path, headers: { 'x-sa-key': b64 }, body: Buffer.from('{}') });
  assert.equal(f.calls.filter((c) => c.url.includes('oauth2')).length, 2);
});

test('regional locations use the regional host', () => {
  assert.equal(hostFor('global'), 'speech.googleapis.com');
  assert.equal(hostFor('asia-southeast1'), 'asia-southeast1-speech.googleapis.com');
});

test('refuses missing key, wrong method and any other path; never calls Google for them', async () => {
  const f = fakes();
  const b = makeBroker({ fetchFn: f.fetchFn, now: f.now });
  assert.equal((await b.handle({ method: 'POST', url: path, headers: {}, body: Buffer.from('') })).status, 401);
  assert.equal((await b.handle({ method: 'GET', url: path, headers: { 'x-sa-key': b64 }, body: Buffer.from('') })).status, 405);
  for (const bad of ['/gcp-speech/v2/projects/p/locations/global/recognizers/_:batchRecognize', '/gcp-speech/v1/speech:recognize', '/other', '/gcp-speech/v2/projects/my-proj-123456/locations/evil.com/recognizers/_:recognize', '/gcp-speech/v2/projects/my-proj-123456/locations/global/recognizers/_:recognize/../x']) {
    assert.equal((await b.handle({ method: 'POST', url: bad, headers: { 'x-sa-key': b64 }, body: Buffer.from('') })).status, 404, bad);
  }
  assert.equal(f.calls.length, 0);
});

test('a bad key gives 502 without leaking it, and Google token failures are reported', async () => {
  const f = fakes();
  const logs = [];
  const b = makeBroker({ fetchFn: f.fetchFn, now: f.now, log: (...a) => logs.push(a.join(' ')) });
  const r = await b.handle({ method: 'POST', url: path, headers: { 'x-sa-key': 'AAAA' }, body: Buffer.from('') });
  assert.equal(r.status, 502);
  assert.ok(!logs.join('\n').includes(b64) && !r.body.includes(pem));
  const failing = makeBroker({ fetchFn: async () => ({ ok: false, status: 400, json: async () => ({ error: 'invalid_grant' }) }), now: f.now });
  const r2 = await failing.handle({ method: 'POST', url: path, headers: { 'x-sa-key': b64 }, body: Buffer.from('') });
  assert.match(r2.body, /invalid_grant/);
});
