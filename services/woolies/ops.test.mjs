import test from 'node:test';
import assert from 'node:assert/strict';
import { ops, validate, resetRecent } from './ops.mjs';

test('validate accepts good requests and rejects bad ones', () => {
  assert.equal(validate({ op: 'search', query: 'milk' }), null);
  assert.equal(validate({ op: 'add', list: 'NanoClaw', items: [{ stockcode: 888140, qty: 2 }] }), null);
  assert.ok(validate({ op: 'nope' }));
  assert.ok(validate({ op: 'search', query: '' }));
  assert.ok(validate({ op: 'search', query: 'x'.repeat(101) }));
  assert.ok(validate({ op: 'add', list: 'ok', items: [] }));
  assert.ok(validate({ op: 'add', list: 'ok', items: [{ stockcode: '1; drop' }] }));
  assert.ok(validate({ op: 'add', list: 'ok', items: [{ stockcode: 5, qty: 100 }] }));
  assert.equal(validate({ op: 'set', list: 'ok', items: [{ stockcode: 5, qty: 12 }] }), null);
  assert.ok(validate({ op: 'add', list: '../etc', items: [{ stockcode: 5 }] }));
  assert.ok(validate({ op: 'show', list: '<script>' }));
  assert.ok(validate(null));
  assert.ok(validate({ op: 'toString' })); // not a prototype method
});

const LISTS = { lists: [{ id: 7, name: 'NanoClaw', count: 2 }, { id: 8, name: 'Other', count: 0 }] };

/** A fake Woolworths tab: a lists endpoint, and one list (id 7) whose contents we track. */
function fakePage(calls, { items = {}, addStatus = 200, editStatus = 200 } = {}) {
  resetRecent();
  const list = new Map(Object.entries(items).map(([k, v]) => [Number(k), v]));
  let created = false;
  return async (fn, arg) => {
    const src = fn.toString();
    if (src.includes('opType')) { created = true; calls.push(['create', arg]); return { status: 200 }; }
    if (src.includes('/Items')) {
      calls.push(['addOne', arg]);
      if (addStatus === 200) list.set(arg.stockcode, 1);
      return { status: addStatus };
    }
    if (src.includes('Edit/Product')) {
      calls.push(['setQty', arg]);
      if (editStatus === 200) list.set(arg.stockcode, arg.qty);
      return { status: editStatus };
    }
    if (src.includes("fetch('/api/v3/ui/savedlists')")) return created ? { lists: [...LISTS.lists, { id: 9, name: 'Fresh', count: 0 }] } : LISTS;
    if (src.includes('savedlists/products')) return { total: list.size, items: [...list].map(([stockcode, qty]) => ({ stockcode, name: 'P' + stockcode, qty })) };
    return { error: 'unexpected call' };
  };
}

test('add puts a new item on the list at the requested quantity', async () => {
  const calls = [];
  const r = await ops.add({ op: 'add', list: 'nanoclaw', items: [{ stockcode: 111, qty: 3 }, { stockcode: 222 }] }, fakePage(calls));
  assert.deepEqual(r.results.map((x) => [x.stockcode, x.quantity]), [[111, 3], [222, 1]]);
  assert.deepEqual(r.added, [111, 222]);
  assert.ok(calls.some((c) => c[0] === 'setQty' && c[1].stockcode === 111 && c[1].qty === 3));
  assert.ok(!calls.some((c) => c[0] === 'setQty' && c[1].stockcode === 222)); // 1 needs no edit
});

test('add is additive on an item already on the list; set is exact', async () => {
  const a = await ops.add({ op: 'add', list: 'NanoClaw', items: [{ stockcode: 5, qty: 2 }] }, fakePage([], { items: { 5: 3 } }));
  assert.equal(a.results[0].quantity, 5);
  const s = await ops.set({ op: 'set', list: 'NanoClaw', items: [{ stockcode: 5, qty: 2 }] }, fakePage([], { items: { 5: 3 } }));
  assert.equal(s.results[0].quantity, 2);
});

test('the same product twice in one request is summed', async () => {
  const r = await ops.add({ op: 'add', list: 'NanoClaw', items: [{ stockcode: 9, qty: 1 }, { stockcode: 9, qty: 2 }] }, fakePage([]));
  assert.equal(r.results.length, 1);
  assert.equal(r.results[0].quantity, 3);
});

test('add to an unknown list fails unless create is set', async () => {
  await assert.rejects(ops.add({ op: 'add', list: 'Fresh', items: [{ stockcode: 1 }] }, fakePage([])), /no list called/);
  const calls = [];
  const r = await ops.add({ op: 'add', list: 'Fresh', create: true, items: [{ stockcode: 1 }] }, fakePage(calls));
  assert.equal(r.list, 'Fresh');
  assert.ok(calls.some((c) => c[0] === 'create'));
});

test('failed adds are reported, not hidden', async () => {
  const r = await ops.add({ op: 'add', list: 'NanoClaw', items: [{ stockcode: 5 }] }, fakePage([], { addStatus: 500 }));
  assert.deepEqual(r.added, []);
  assert.equal(r.failed.length, 1);
});

test('two quick adds stack even if the site list view has not caught up', async () => {
  const calls = [];
  const page = fakePage(calls);
  const staleShow = async (fn, arg) => (fn.toString().includes('savedlists/products') ? { total: 0, items: [] } : page(fn, arg));
  await ops.add({ op: 'add', list: 'NanoClaw', items: [{ stockcode: 77, qty: 2 }] }, staleShow);
  const r = await ops.add({ op: 'add', list: 'NanoClaw', items: [{ stockcode: 77, qty: 1 }] }, staleShow);
  assert.equal(r.results[0].quantity, 3);
});
