import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';

import { SpokenLog, TAIL_MS } from './echo.ts';

const tmp = () => path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'echo-')), 'spoken.json');
const REPLY = "Sure thing, I've checked the flights and the cheapest option from Sydney to Auckland on the fourth is six hundred and fifty dollars.";

test('what an agent just said, heard back through the microphone, is an echo', () => {
  const log = new SpokenLog(tmp());
  log.record('jack', REPLY, 1000);
  assert.equal(log.echoOf("sure thing i've checked the flights and the cheapest option from sydney to auckland", 6000), 'jack');
});

test('a garbled partial transcript of the reply is still an echo', () => {
  const log = new SpokenLog(tmp());
  log.record('jimmy', REPLY, 1000);
  assert.equal(log.echoOf('check the flights the cheapest option from sydney to oakland on the fourth is 650 dollars', 7000), 'jimmy');
});

test('George speaking about something else is not an echo', () => {
  const log = new SpokenLog(tmp());
  log.record('jack', REPLY, 1000);
  assert.equal(log.echoOf('can you also book the rental car for the whole week please', 6000), null);
  assert.equal(log.echoOf('what about the cheapest hotel near the airport', 6000), null);
});

test('short replies are never treated as an echo', () => {
  const log = new SpokenLog(tmp());
  log.record('jack', 'Okay, done.', 1000);
  assert.equal(log.echoOf('okay done', 2000), null);
  assert.equal(log.echoOf('yes please', 2000), null);
});

test('only recent speech counts; the same words later are George', () => {
  const log = new SpokenLog(tmp());
  const id = log.record('jack', REPLY, 1000);
  log.finish(id, 9000);
  const same = "sure thing i've checked the flights and the cheapest option from sydney to auckland";
  assert.equal(log.echoOf(same, 9000 + TAIL_MS - 1), 'jack');
  assert.equal(log.echoOf(same, 9000 + TAIL_MS + 5000), null);
});

test('a missing or broken file filters nothing', () => {
  const f = tmp();
  const log = new SpokenLog(f);
  assert.equal(log.echoOf('sure thing i have checked the flights and the cheapest option', 1000), null);
  fs.writeFileSync(f, 'not json');
  assert.equal(log.echoOf('sure thing i have checked the flights and the cheapest option', 1000), null);
});
