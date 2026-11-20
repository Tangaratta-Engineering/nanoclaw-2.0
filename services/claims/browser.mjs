// Drives George's signed-in Peoplecare tab (Chrome DevTools Protocol on 127.0.0.1:9223) through the normal
// "Submit claim" screens by clicking what a person would click. No dependencies (Node 22 has fetch + WebSocket).
// Peoplecare's access token lasts 30 minutes and the site renews it while the page is in use, so a keep-alive
// touches the page every 10 minutes. Deep links do not work on this site: always start from Home.
export const SITE = 'oms.peoplecare.com.au';

class Cdp {
  constructor(ws) { this.ws = ws; this.id = 0; this.pending = new Map(); ws.onmessage = (e) => { const m = JSON.parse(e.data); this.pending.get(m.id)?.(m); }; }
  send(method, params = {}) {
    return new Promise((res, rej) => {
      const id = ++this.id;
      const t = setTimeout(() => { this.pending.delete(id); rej(new Error('timed out talking to Peoplecare')); }, 30000);
      this.pending.set(id, (m) => { clearTimeout(t); this.pending.delete(id); m.error ? rej(new Error(m.error.message)) : res(m.result); });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }
  async eval(fn, arg) {
    const r = await this.send('Runtime.evaluate', { expression: `(${fn.toString()})(${JSON.stringify(arg ?? null)})`, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) throw new Error('page error: ' + String(r.exceptionDetails.exception?.description || 'unknown').split('\n')[0].slice(0, 160));
    return r.result.value;
  }
  close() { try { this.ws.close(); } catch { /* ignore */ } }
}

export function makeBrowser({ cdp = process.env.CLAIMS_CDP || 'http://127.0.0.1:9223', sleep = (ms) => new Promise((r) => setTimeout(r, ms)) } = {}) {
  async function open() {
    const tabs = await (await fetch(`${cdp}/json`)).json();
    const t = tabs.find((x) => x.type === 'page' && x.url.includes(SITE));
    if (!t) throw new Error('no Peoplecare tab is open in the claims Chrome: George needs to sign in again');
    const ws = new WebSocket(t.webSocketDebuggerUrl);
    await new Promise((res, rej) => { ws.onopen = res; ws.onerror = () => rej(new Error('cannot reach the claims Chrome')); });
    return new Cdp(ws);
  }
  const where = (c) => c.eval(() => ({ path: location.pathname, text: document.body ? document.body.innerText : '' }));
  async function waitPath(c, want, ms = 20000) {
    const end = Date.now() + ms;
    for (;;) {
      const w = await where(c);
      if (w.path.startsWith(want)) return w;
      if (Date.now() > end) throw new Error(`Peoplecare did not reach ${want} (stuck on ${w.path.slice(0, 30)})`);
      await sleep(400);
    }
  }
  const clickButton = (c, label) => c.eval((l) => {
    const b = [...document.querySelectorAll('button')].find((x) => x.innerText.trim().toLowerCase() === l.toLowerCase() && !x.disabled);
    if (!b) throw new Error('no ' + l + ' button');
    b.click(); return true;
  }, label);

  /** Signed in = the page shows the member's own home screen, not the login redirect. */
  async function session() {
    const c = await open();
    try {
      const w = await where(c);
      const signedIn = /member number/i.test(w.text) || w.path.startsWith('/addclaim');
      return { signed_in: signedIn, page: w.path.slice(0, 30) };
    } finally { c.close(); }
  }
  /** Keep the session renewing: go Home (a normal page load) unless a claim is part-way through. */
  async function keepAlive() {
    const c = await open();
    try {
      const w = await where(c);
      if (w.path.startsWith('/addclaim')) return { skipped: 'claim in progress' };
      await c.eval(() => { const a = [...document.querySelectorAll('a')].find((x) => x.innerText.trim() === 'Home'); if (a) a.click(); });
      await sleep(3000);
      return session();
    } finally { c.close(); }
  }
  async function leave() {
    const c = await open();
    try { await c.eval(() => { const a = [...document.querySelectorAll('a')].find((x) => x.innerText.trim() === 'Home'); if (a) a.click(); }); } finally { c.close(); }
  }

  /** Home -> Submit claim -> intro -> attach PDF -> reference -> Review page. Stops there: never submits. */
  async function prepare({ files, reference }) {
    const c = await open();
    try {
      let w = await where(c);
      if (!/member number|submit claim/i.test(w.text) && !w.path.startsWith('/addclaim')) throw new Error('Peoplecare is not signed in: George needs to sign in again');
      if (w.path.startsWith('/addclaim')) { await c.eval(() => { const a = [...document.querySelectorAll('a')].find((x) => x.innerText.trim() === 'Home'); if (a) a.click(); }); await waitPath(c, '/home'); }
      await clickButton(c, 'Submit claim');             // the green button at the top opens the claim form
      await waitPath(c, '/addclaim/intro');
      await c.eval(() => document.querySelector('button[type=submit]').click());
      await waitPath(c, '/addclaim/images');
      await c.send('DOM.enable');
      const doc = await c.send('DOM.getDocument', { depth: -1 });
      const q = await c.send('DOM.querySelector', { nodeId: doc.root.nodeId, selector: 'input[type=file]' });
      if (!q.nodeId) throw new Error('could not find the upload box');
      await c.send('DOM.setFileInputFiles', { nodeId: q.nodeId, files });
      const end = Date.now() + 20000;
      for (;;) {
        const n = await c.eval(() => document.querySelectorAll('.upload__uploaded-item').length);
        if (n >= files.length) break;
        if (Date.now() > end) throw new Error('the PDF did not attach');
        await sleep(400);
      }
      await clickButton(c, 'Next');
      await waitPath(c, '/addclaim/referenceentry');
      await c.eval((ref) => {
        const i = document.querySelector('input[type=text]'); i.focus();
        Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(i, ref);
        i.dispatchEvent(new Event('input', { bubbles: true })); i.dispatchEvent(new Event('change', { bubbles: true })); i.blur();
      }, reference);
      await sleep(400);
      await clickButton(c, 'Next');
      w = await waitPath(c, '/addclaim/summary');
      if (!w.text.includes(reference)) throw new Error('the Review page does not show the reference: not continuing');
      const member = (w.text.match(/MEMBER NUMBER\s*\n?\s*(\d+)/i) || [])[1];
      return { page: '/addclaim/summary', member_number: member || null, reference, receipts: files.length };
    } finally { c.close(); }
  }

  /** Only valid on the Review page that prepare() left behind: tick the terms box, press Submit, read the reference. */
  async function submit({ reference, files }) {
    const c = await open();
    try {
      const w = await where(c);
      if (!w.path.startsWith('/addclaim/summary') || !w.text.includes(reference)) throw new Error('the Review page for this claim is not open any more: prepare it again');
      const ok = await c.eval(() => {
        const box = [...document.querySelectorAll('input[type=checkbox]')].find((b) => /agree/i.test((b.closest('div,label,section')?.innerText || '')) && !/email receipt/i.test(b.closest('div,label')?.innerText || ''));
        if (!box) return false;
        if (!box.checked) box.click();
        return box.checked;
      });
      if (!ok) throw new Error('could not tick "I agree with the above terms"');
      await sleep(400);
      await c.eval(() => {
        const b = [...document.querySelectorAll('button')].filter((x) => x.innerText.trim() === 'Submit claim').pop();
        if (!b || b.disabled) throw new Error('the Submit claim button is not available');
        b.click();
      });
      const end = Date.now() + 40000;
      for (;;) {
        const t = (await where(c)).text;
        const m = t.match(/reference number is (Claim_\d+)/i);
        if (m) return m[1];
        if (/error|went wrong|try again/i.test(t) && !/terms/i.test(t)) throw new Error('Peoplecare showed an error after Submit: check Claims > History before retrying');
        if (Date.now() > end) throw new Error('no confirmation seen from Peoplecare: check Claims > History before retrying');
        await sleep(800);
      }
    } finally { c.close(); }
  }
  return { session, keepAlive, prepare, submit, leave };
}
