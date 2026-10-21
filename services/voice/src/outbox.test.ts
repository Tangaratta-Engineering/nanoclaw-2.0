import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { DatabaseSync } from 'node:sqlite';

import { OutboxWatcher, textOf } from './outbox.ts';

function mk(): { dir: string; db: DatabaseSync } {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ob-'));
  fs.mkdirSync(path.join(dir, 's1'));
  const db = new DatabaseSync(path.join(dir, 's1', 'outbound.db'));
  db.exec('create table messages_out (seq integer primary key, platform_id text, content text)');
  return { dir, db };
}
const add = (db: DatabaseSync, seq: number, pid: string, text: string) =>
  db.prepare('insert into messages_out values (?,?,?)').run(seq, pid, JSON.stringify({ text }));

test('speaks only new DM messages while armed', () => {
  const { dir, db } = mk();
  add(db, 2, 'dm', 'old news');
  const w = new OutboxWatcher(dir, 'dm');
  const got: string[] = [];
  w.onText = (t) => got.push(t);
  w.start();
  add(db, 4, 'dm', 'unarmed notification');
  w.poll();
  assert.deepEqual(got, []);
  w.arm(60_000);
  add(db, 6, 'other', 'elsewhere');
  add(db, 8, 'dm', 'spoken reply');
  w.poll();
  assert.deepEqual(got, ['spoken reply']);
  w.stop();
});

test('textOf handles non-text content', () => {
  assert.equal(textOf('{"text":" hi "}'), ' hi ');
  assert.equal(textOf('{"file":"x"}'), null);
  assert.equal(textOf('nope'), null);
});
