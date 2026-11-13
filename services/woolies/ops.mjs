// The operations the bridge can run, and validation of requests. Each op runs `inPage(fn, arg)`, where `fn`
// is serialised and executed inside the signed-in Woolworths tab, so it must not use anything from this module.

const LIST_RE = /^[\w .&'()-]{1,60}$/;
const NEEDS_LIST = new Set(['show', 'add', 'set', 'remove', 'clear']);

export function validate(req) {
  if (!req || typeof req !== 'object' || typeof req.op !== 'string' || !Object.hasOwn(ops, req.op)) return 'unknown op';
  if (['search', 'history'].includes(req.op) && (typeof req.query !== 'string' || req.query.length < 1 || req.query.length > 100)) return 'query must be 1-100 characters';
  if (req.limit !== undefined && !(Number.isInteger(req.limit) && req.limit >= 1 && req.limit <= 20)) return 'limit must be 1-20';
  if (NEEDS_LIST.has(req.op) && (typeof req.list !== 'string' || !LIST_RE.test(req.list))) return 'list name must be 1-60 plain characters';
  if (req.op === 'remove') {
    if (!Array.isArray(req.items) || req.items.length < 1 || req.items.length > 25) return 'items must be 1-25 entries';
    for (const it of req.items) if (!it || !Number.isInteger(it.stockcode) || it.stockcode < 1 || it.stockcode > 99999999) return 'each item needs a numeric stockcode';
  }
  if (req.op === 'clear' && req.confirm !== true) return 'clear needs confirm: true';
  if (req.op === 'add' || req.op === 'set') {
    if (!Array.isArray(req.items) || req.items.length < 1 || req.items.length > 25) return 'items must be 1-25 entries';
    for (const it of req.items) {
      if (!it || !Number.isInteger(it.stockcode) || it.stockcode < 1 || it.stockcode > 99999999) return 'each item needs a numeric stockcode';
      if (!Number.isInteger(it.qty ?? 1) || (it.qty ?? 1) < 1 || (it.qty ?? 1) > 99) return 'qty must be 1-99';
    }
  }
  return null;
}

// ---- code that runs inside the page -------------------------------------------------------------

const pageHelpers = `
  const J = { 'content-type': 'application/json' };
  const post = (u, b) => fetch(u, { method: 'POST', headers: J, body: JSON.stringify(b) });
  const prod = (p) => ({ stockcode: p.Stockcode, name: p.DisplayName || p.Name, brand: p.Brand || null, size: p.PackageSize || null,
    price: p.Price ?? null, cup: p.CupString || null, boughtBefore: !!p.HasBeenBoughtBefore, special: !!p.IsOnSpecial, available: p.IsAvailable !== false && p.IsInStock !== false });
`;

function page(body) {
  // Build a function whose source carries the helpers; inPage() stringifies it.
  return new Function('arg', `return (async () => { ${pageHelpers} ${body} })();`);
}

const searchFn = page(`
  const r = await post('/apis/ui/Search/products', { Filters: [], IsSpecial: false, Location: '/shop/search/products?searchTerm=' + arg.query,
    PageNumber: 1, PageSize: arg.limit, SearchTerm: arg.query, SortType: 'TraderRelevance' });
  if (r.status !== 200) return { error: 'search failed (HTTP ' + r.status + ')' };
  const j = await r.json();
  return { items: (j.Products || []).flatMap((x) => x.Products || []).slice(0, arg.limit).map(prod) };
`);

const historyFn = page(`
  const r = await post('/api/v3/ui/pastshops/AllProducts', { PageSize: String(arg.limit), PageNumber: '1', SearchTerm: arg.query, SortType: 'Aisle', SortType2: '',
    isSpecial: false, useV2Tags: true, location: '/shop/mylists/pastshops/everything', Filters: [], IncludeOnline: true, IncludeInstore: false });
  if (r.status !== 200) return { error: 'history failed (HTTP ' + r.status + ')' };
  const j = await r.json();
  return { total: j.TotalRecordCount, items: (j.Items || []).map(prod) };
`);

const listsFn = page(`
  const r = await fetch('/api/v3/ui/savedlists');
  if (r.status !== 200) return { error: r.status === 401 || r.status === 403 ? 'not signed in' : 'lists failed (HTTP ' + r.status + ')' };
  const j = await r.json();
  if (!j.success) return { error: 'not signed in' };
  return { lists: j.data.q.map((l) => ({ id: l.id, name: l.name, count: l.productCount })) };
`);

const showFn = page(`
  const r = await post('/api/v3/ui/savedlists/products', { listId: arg.id, pagingParams: { sortType: 'Aisle', sortType2: '', pageNumber: 1, pageSize: 36, isSpecial: false } });
  if (r.status !== 200) return { error: 'could not read the list (HTTP ' + r.status + ')' };
  const j = await r.json();
  return { total: j.TotalRecordCount, items: (j.Items || []).map((p) => ({ ...prod(p), qty: p.DisplayQuantity ?? 1 })) };
`);

// The list's own record: one row per product with the row id that deletes need, and the quantity.
const detailFn = page(`
  const r = await fetch('/api/v3/ui/savedlists/' + arg.id);
  if (r.status !== 200) return { error: 'could not read the list (HTTP ' + r.status + ')' };
  const j = await r.json();
  return { rows: (j.data.q.products || []).map((p) => ({ rowId: p.id, stockcode: Number(p.articleNumber), qty: p.quantity })) };
`);

const deleteFn = page(`
  const r = await post('/api/v3/ui/savedlists', { opType: 'UPDATE', id: arg.id, products: arg.rowIds.map((id) => ({ opType: 'DELETE', id })) });
  return { status: r.status };
`);

const createFn = page(`
  const r = await post('/api/v3/ui/savedlists', { opType: 'CREATE', name: arg.name, color: '#00AB4E' });
  return { status: r.status };
`);

const addOneFn = page(`
  const r = await post('/apis/ui/mylists/' + arg.id + '/Items', { Quantity: 1, Source: 'RR', StockCode: arg.stockcode });
  return { status: r.status };
`);

// The site's own quantity stepper on a list: sets the quantity of one list item (absolute, not "add").
const setQtyFn = page(`
  const r = await post('/apis/ui/mylists/Edit/Product', { stockcode: arg.stockcode, quantity: arg.qty, listId: arg.id });
  return { status: r.status };
`);

async function findList(req, inPage, create) {
  let r = await inPage(listsFn, {});
  if (r.error) throw new Error(r.error);
  const want = req.list.toLowerCase();
  let hit = r.lists.find((l) => l.name.toLowerCase() === want);
  if (!hit && create) {
    const c = await inPage(createFn, { name: req.list });
    if (c.status !== 200) throw new Error(`could not create the list (HTTP ${c.status})`);
    r = await inPage(listsFn, {});
    hit = r.lists.find((l) => l.name.toLowerCase() === want);
  }
  if (!hit) throw new Error(`no list called "${req.list}" (use "lists" to see them)`);
  return hit;
}

const unwrap = (r) => { if (r.error) throw new Error(r.error); return r; };

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Woolworths' list view can lag the edits just made by 20 seconds or more, so remember what we set ourselves
// and prefer it over the (stale) read-back for 2 minutes. Keeps "add 2" then "add 1" a few seconds apart right.
const recent = new Map(); // `${listId}:${stockcode}` -> { qty, at }
const RECENT_MS = 120_000;
export const resetRecent = () => recent.clear(); // tests

/** Quantities on the list right now: Map(stockcode -> {qty, name}), with our own recent edits laid over the site's view. */
async function listQuantities(id, inPage) {
  const r = unwrap(await inPage(showFn, { id }));
  const m = new Map(r.items.map((i) => [i.stockcode, { qty: i.qty, name: i.name }]));
  for (const [k, v] of recent) {
    if (Date.now() - v.at > RECENT_MS) { recent.delete(k); continue; }
    const [lid, sc] = k.split(':').map(Number);
    if (lid !== id) continue;
    if (v.qty === 0) m.delete(sc);
    else m.set(sc, { qty: v.qty, name: m.get(sc)?.name ?? v.name ?? null });
  }
  return m;
}

/**
 * add (additive=true): each qty is ADDED to what the list already holds for that product.
 * set (additive=false): each qty becomes the exact quantity on the list.
 * Works out the target quantity itself, applies it with the site's own list stepper and reports the quantity it set.
 */
async function changeQuantities(req, inPage, additive) {
  const l = await findList(req, inPage, req.create === true);
  const want = new Map();
  for (const i of req.items) want.set(i.stockcode, (additive ? (want.get(i.stockcode) ?? 0) : 0) + (i.qty ?? 1));
  const before = await listQuantities(l.id, inPage);
  const failed = [];
  const results = [];
  for (const [stockcode, qty] of want) {
    const have = before.get(stockcode)?.qty ?? 0;
    const target = additive ? have + qty : qty;
    let ok = true;
    if (have === 0) {
      const a = await inPage(addOneFn, { id: l.id, stockcode });
      if (a.status !== 200) { failed.push({ stockcode, status: a.status }); ok = false; }
      else await sleep(400);
    }
    if (ok && (target !== 1 || have > 0)) {
      const e = await inPage(setQtyFn, { id: l.id, stockcode, qty: target });
      if (e.status !== 200) { failed.push({ stockcode, status: e.status }); ok = false; }
    }
    if (ok) recent.set(`${l.id}:${stockcode}`, { qty: target, at: Date.now(), name: before.get(stockcode)?.name ?? null });
    results.push({ stockcode, name: before.get(stockcode)?.name ?? null, quantity: ok ? target : null });
    await sleep(250 + Math.random() * 250);
  }
  // names for newly added products (the list view lags, so this is best effort)
  await sleep(1200);
  const now = await listQuantities(l.id, inPage).catch(() => new Map());
  for (const r of results) r.name = r.name ?? now.get(r.stockcode)?.name ?? null;
  return { list: l.name, results, added: results.filter((r) => r.quantity).map((r) => r.stockcode), failed };
}

/** Removing is only allowed on the agents' own list (NanoClaw), never on George's real lists. */
const deletableLists = () => (process.env.WOOLIES_DELETE_LISTS || 'NanoClaw').split(',').map((x) => x.trim().toLowerCase());

/** Remove products (or everything, when `stockcodes` is null) from a list. */
async function removeFromList(req, inPage, stockcodes) {
  if (!deletableLists().includes(req.list.toLowerCase())) throw new Error(`I only remove items from the NanoClaw list, not "${req.list}". George can edit that one in the app`);
  const l = await findList(req, inPage, false);
  const d = unwrap(await inPage(detailFn, { id: l.id }));
  const rows = stockcodes ? d.rows.filter((r) => stockcodes.includes(r.stockcode)) : d.rows;
  const missing = stockcodes ? stockcodes.filter((sc) => !d.rows.some((r) => r.stockcode === sc)) : [];
  if (rows.length) {
    const r = await inPage(deleteFn, { id: l.id, rowIds: rows.map((x) => x.rowId) });
    if (r.status !== 200) throw new Error(`could not remove items (HTTP ${r.status})`);
    for (const x of rows) recent.set(`${l.id}:${x.stockcode}`, { qty: 0, at: Date.now(), name: null });
  }
  return { list: l.name, removed: rows.map((x) => x.stockcode), notOnList: missing };
}

/** Woolworths' own products have codes up to 8 digits; 10-digit codes are Marketplace items sold by third parties. George does not want those, so they are removed from results (and counted, so the agent can say so). */
export const MAX_OWN_STOCKCODE = 99999999;
const dropMarketplace = (r) => {
  if (!Array.isArray(r?.items)) return r;
  const own = r.items.filter((i) => !(Number(i.stockcode) > MAX_OWN_STOCKCODE));
  return { ...r, items: own, marketplaceHidden: r.items.length - own.length };
};

export const ops = {
  async status(_req, inPage) {
    const r = await inPage(listsFn, {});
    return { signedIn: !r.error, detail: r.error || `${r.lists.length} lists` };
  },
  async search(req, inPage) { return dropMarketplace(unwrap(await inPage(searchFn, { query: req.query, limit: req.limit ?? 6 }))); },
  async history(req, inPage) { return dropMarketplace(unwrap(await inPage(historyFn, { query: req.query, limit: req.limit ?? 6 }))); },
  async lists(_req, inPage) { return unwrap(await inPage(listsFn, {})); },
  async show(req, inPage) {
    const l = await findList(req, inPage, false);
    return { list: l.name, ...unwrap(await inPage(showFn, { id: l.id })) };
  },
  async add(req, inPage) { return changeQuantities(req, inPage, true); },
  async set(req, inPage) { return changeQuantities(req, inPage, false); },
  async remove(req, inPage) { return removeFromList(req, inPage, req.items.map((i) => i.stockcode)); },
  async clear(req, inPage) { return removeFromList(req, inPage, null); },
};
