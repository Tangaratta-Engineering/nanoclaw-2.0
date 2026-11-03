import test from 'node:test';
import assert from 'node:assert/strict';
import { ops, validate } from './ops.mjs';

test('validate accepts good requests and rejects bad ones', () => {
  assert.equal(validate({ op: 'search', query: 'milk' }), null);
  assert.equal(validate({ op: 'add', list: 'NanoClaw', items: [{ stockcode: 888140, qty: 2 }] }), null);
  assert.ok(validate({ op: 'nope' }));
  assert.ok(validate({ op: 'search', query: '' }));
  assert.ok(validate({ op: 'search', query: 'x'.repeat(101) }));
  assert.ok(validate({ op: 'add', list: 'ok', items: [] }));
  assert.ok(validate({ op: 'add', list: 'ok', items: [{ stockcode: '1; drop' }] }));
  assert.ok(validate({ op: 'add', list: 'ok', items: [{ stockcode: 5, qty: 99 }] }));
  assert.ok(validate({ op: 'add', list: '../etc', items: [{ stockcode: 5 }] }));
  assert.ok(validate({ op: 'show', list: '<script>' }));
  assert.ok(validate(null));
  assert.ok(validate({ op: 'toString' })); // not a prototype method
});

const LISTS = { lists: [{ id: 7, name: 'NanoClaw', count: 2 }, { id: 8, name: 'Other', count: 0 }] };
function fakePage(calls, { lists = LISTS, createStatus = 200, addStatus = 200 } = {}) {
  let created = false;
  return async (fn, arg) => {
    const src = fn.toString();
    calls.push([src.includes('savedlists\'') && !src.includes('opType') ? 'lists' : src.includes('opType') ? 'create' : src.includes('Items') ? 'add' : 'other', arg]);
    if (src.includes('opType')) { created = true; return { status: createStatus }; }
    if (src.includes('/Items')) return { results: arg.items.map((i) => ({ stockcode: i.stockcode, status: addStatus })) };
    if (src.includes("fetch('/api/v3/ui/savedlists')")) return created ? { lists: [...lists.lists, { id: 9, name: 'Fresh', count: 0 }] } : lists;
    return { error: 'unexpected call' };
  };
}

test('add resolves the list name case-insensitively and adds items', async () => {
  const calls = [];
  const r = await ops.add({ op: 'add', list: 'nanoclaw', items: [{ stockcode: 111, qty: 2 }, { stockcode: 222 }] }, fakePage(calls));
  assert.deepEqual(r.added, [111, 222]);
  const add = calls.find((c) => c[0] === 'add');
  assert.deepEqual(add[1], { id: 7, items: [{ stockcode: 111, qty: 2 }, { stockcode: 222, qty: 1 }] });
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
