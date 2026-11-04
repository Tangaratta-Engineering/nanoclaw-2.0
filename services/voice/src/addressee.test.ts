import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import { AddresseeState, isForAgent, STICKY_MS } from './addressee.ts';

const fresh = () => new AddresseeState(path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'addr-')), 'a.json'));

test('unnamed speech with nobody addressed goes to the default agent only', () => {
  const s = fresh();
  assert.equal(isForAgent('tiff', [], s), true);
  assert.equal(isForAgent('jack', [], s), false);
  assert.equal(isForAgent('jimmy', [], s), false);
});

test('naming an agent makes the follow-ups its own until another is named', () => {
  const s = fresh();
  const t = 1_000_000;
  assert.equal(isForAgent('jack', ['jack'], s, t), true);
  assert.equal(isForAgent('tiff', ['jack'], s, t), false);
  // unnamed follow-up questions
  assert.equal(isForAgent('jack', [], s, t + 30_000), true);
  assert.equal(isForAgent('tiff', [], s, t + 30_000), false);
  assert.equal(isForAgent('jimmy', [], s, t + 30_000), false);
  // now George turns to Tiff
  assert.equal(isForAgent('tiff', ['tiff'], s, t + 60_000), true);
  assert.equal(isForAgent('jack', [], s, t + 70_000), false);
  assert.equal(isForAgent('tiff', [], s, t + 70_000), true);
});

test('naming two agents wakes both', () => {
  const s = fresh();
  assert.equal(isForAgent('tiff', ['tiff', 'jimmy'], s), true);
  assert.equal(isForAgent('jimmy', ['tiff', 'jimmy'], s), true);
  assert.equal(isForAgent('jack', ['tiff', 'jimmy'], s), false);
});

test('the conversation stays with the agent while it keeps going, and lapses after a quiet spell', () => {
  const s = fresh();
  const t = 5_000_000;
  isForAgent('jack', ['jack'], s, t);
  // five minutes later, still talking: keeps it alive
  assert.equal(isForAgent('jack', [], s, t + 5 * 60_000), true);
  assert.equal(isForAgent('jack', [], s, t + 10 * 60_000), true);
  // a gap longer than the window: back to the default agent
  assert.equal(isForAgent('jack', [], s, t + 10 * 60_000 + STICKY_MS + 1000), false);
  assert.equal(isForAgent('tiff', [], s, t + 10 * 60_000 + STICKY_MS + 1000), true);
});

test('a missing or broken state file never breaks a call', () => {
  const s = new AddresseeState('/dev/null/not-a-dir/a.json');
  s.remember(['jack']); // must not throw
  assert.deepEqual(s.current(), []);
  assert.equal(isForAgent('tiff', [], s), true);
});
