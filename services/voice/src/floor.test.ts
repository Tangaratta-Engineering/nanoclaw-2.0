import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';

import { Floor, STALE_MS } from './floor.ts';

const tmp = () => path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'floor-')), 'floor.json');

test('only one agent holds the floor at a time', () => {
  const f = new Floor(tmp());
  assert.equal(f.tryAcquire('tiff'), true);
  assert.equal(f.tryAcquire('jack'), false);
  assert.equal(f.holder(), 'tiff');
  assert.equal(f.tryAcquire('tiff'), true); // the holder keeps it
});

test('release hands the floor over; only the holder can release', () => {
  const f = new Floor(tmp());
  f.tryAcquire('tiff');
  f.release('jack');
  assert.equal(f.holder(), 'tiff');
  f.release('tiff');
  assert.equal(f.tryAcquire('jack'), true);
});

test('a lock nobody refreshed is taken over', () => {
  const f = new Floor(tmp());
  const t = 1_000_000;
  f.tryAcquire('tiff', t);
  assert.equal(f.tryAcquire('jack', t + STALE_MS - 1), false);
  assert.equal(f.tryAcquire('jack', t + STALE_MS + 1), true);
});

test('acquire waits for the holder, then proceeds', async () => {
  const f = new Floor(tmp());
  f.tryAcquire('tiff');
  let n = 0;
  const waited = await f.acquire('jack', 5_000, async () => {
    if (++n === 3) f.release('tiff');
  });
  assert.equal(waited, 'tiff');
  assert.equal(f.holder(), 'jack');
});

test('acquire gives up waiting after the limit', async () => {
  const f = new Floor(tmp());
  f.tryAcquire('tiff');
  const waited = await f.acquire('jack', 0, async () => {});
  assert.equal(waited, 'tiff');
});
