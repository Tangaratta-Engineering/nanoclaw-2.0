import test from 'node:test';
import assert from 'node:assert/strict';

import { Speaker } from './tts.ts';

const fake = (name: string, fail = false) => {
  const calls: string[] = [];
  return {
    calls,
    warmed: 0,
    stopped: 0,
    warm() { this.warmed++; },
    async synthesize(t: string) { calls.push(t); if (fail) throw new Error(`${name} down`); return `${name}:${t}`; },
    stop() { this.stopped++; },
  };
};

test('without a Google voice it is just Piper', async () => {
  const piper = fake('piper');
  const s = new Speaker(piper, null);
  s.warm();
  assert.equal(await s.synthesize('hi'), 'piper:hi');
  assert.equal(piper.warmed, 1);
});

test('with Google it warms only Google and uses it', async () => {
  const piper = fake('piper'), google = fake('google');
  const s = new Speaker(piper, google);
  s.warm();
  assert.equal(await s.synthesize('hi'), 'google:hi');
  assert.equal(google.warmed, 1);
  assert.equal(piper.warmed, 0);
  assert.deepEqual(piper.calls, []);
});

test('a Google failure falls back to Piper for that sentence', async () => {
  const piper = fake('piper'), google = fake('google', true);
  const s = new Speaker(piper, google);
  assert.equal(await s.synthesize('one'), 'piper:one');
  assert.equal(google.calls.length, 1);
});

test('after two failures it stays on Piper for a minute, then tries Google again', async () => {
  let t = 1_000_000;
  const piper = fake('piper');
  let broken = true;
  const google = {
    calls: 0, warm() {}, stop() {},
    async synthesize(x: string) { this.calls++; if (broken) throw new Error('down'); return 'google:' + x; },
  };
  const s = new Speaker(piper, google, () => t);
  await s.synthesize('a'); await s.synthesize('b'); // two failures
  assert.equal(google.calls, 2);
  await s.synthesize('c'); await s.synthesize('d'); // paused: Google not even asked
  assert.equal(google.calls, 2);
  t += 61_000; broken = false;
  assert.equal(await s.synthesize('e'), 'google:e');
  assert.equal(google.calls, 3);
});

test('stop stops both workers', () => {
  const piper = fake('piper'), google = fake('google');
  new Speaker(piper, google).stop();
  assert.equal(piper.stopped + google.stopped, 2);
});
