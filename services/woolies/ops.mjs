// The operations the bridge can run, and validation of requests. Each op runs `inPage(fn, arg)`, where `fn`
// is serialised and executed inside the signed-in Woolworths tab, so it must not use anything from this module.

const LIST_RE = /^[\w .&'()-]{1,60}$/;
const NEEDS_LIST = new Set(['show', 'add']);

export function validate(req) {
  if (!req || typeof req !== 'object' || typeof req.op !== 'string' || !Object.hasOwn(ops, req.op)) return 'unknown op';
  if (['search', 'history'].includes(req.op) && (typeof req.query !== 'string' || req.query.length < 1 || req.query.length > 100)) return 'query must be 1-100 characters';
  if (req.limit !== undefined && !(Number.isInteger(req.limit) && req.limit >= 1 && req.limit <= 20)) return 'limit must be 1-20';
  if (NEEDS_LIST.has(req.op) && (typeof req.list !== 'string' || !LIST_RE.test(req.list))) return 'list name must be 1-60 plain characters';
  if (req.op === 'add') {
    if (!Array.isArray(req.items) || req.items.length < 1 || req.items.length > 25) return 'items must be 1-25 entries';
    for (const it of req.items) {
      if (!it || !Number.isInteger(it.stockcode) || it.stockcode < 1 || it.stockcode > 99999999) return 'each item needs a numeric stockcode';
      if (!Number.isInteger(it.qty ?? 1) || (it.qty ?? 1) < 1 || (it.qty ?? 1) > 20) return 'qty must be 1-20';
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
  return { total: j.TotalRecordCount, items: (j.Items || []).map((p) => ({ ...prod(p), qty: p.QuantityInTrolley })) };
`);

const createFn = page(`
  const r = await post('/api/v3/ui/savedlists', { opType: 'CREATE', name: arg.name, color: '#00AB4E' });
  return { status: r.status };
`);

const addFn = page(`
  const out = [];
  for (const it of arg.items) {
    const r = await post('/apis/ui/mylists/' + arg.id + '/Items', { Quantity: it.qty, Source: 'RR', StockCode: it.stockcode });
    out.push({ stockcode: it.stockcode, status: r.status });
    await new Promise((res) => setTimeout(res, 250 + Math.random() * 250));
  }
  return { results: out };
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

export const ops = {
  async status(_req, inPage) {
    const r = await inPage(listsFn, {});
    return { signedIn: !r.error, detail: r.error || `${r.lists.length} lists` };
  },
  async search(req, inPage) { return unwrap(await inPage(searchFn, { query: req.query, limit: req.limit ?? 6 })); },
  async history(req, inPage) { return unwrap(await inPage(historyFn, { query: req.query, limit: req.limit ?? 6 })); },
  async lists(_req, inPage) { return unwrap(await inPage(listsFn, {})); },
  async show(req, inPage) {
    const l = await findList(req, inPage, false);
    return { list: l.name, ...unwrap(await inPage(showFn, { id: l.id })) };
  },
  async add(req, inPage) {
    const l = await findList(req, inPage, req.create === true);
    const items = req.items.map((i) => ({ stockcode: i.stockcode, qty: i.qty ?? 1 }));
    const r = unwrap(await inPage(addFn, { id: l.id, items }));
    return { list: l.name, added: r.results.filter((x) => x.status === 200).map((x) => x.stockcode), failed: r.results.filter((x) => x.status !== 200) };
  },
};
