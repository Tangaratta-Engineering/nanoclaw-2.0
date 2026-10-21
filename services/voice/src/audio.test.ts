import assert from 'node:assert/strict';
import { test } from 'node:test';

import { durationSecs, rms, toMono16k, wav16kMono } from './audio.ts';

test('downsamples 48k stereo to 16k mono', () => {
  const pcm = Buffer.alloc(48000 * 4); // 1 s
  for (let i = 0; i < 48000; i++) {
    pcm.writeInt16LE(1000, i * 4);
    pcm.writeInt16LE(3000, i * 4 + 2);
  }
  const m = toMono16k(pcm);
  assert.equal(m.length, 16000);
  assert.equal(m[0], 2000);
  assert.equal(durationSecs(m), 1);
});

test('wav header is well formed', () => {
  const w = wav16kMono(new Int16Array(16000));
  assert.equal(w.toString('ascii', 0, 4), 'RIFF');
  assert.equal(w.readUInt32LE(24), 16000);
  assert.equal(w.readUInt32LE(40), 32000);
  assert.equal(w.length, 44 + 32000);
});

test('rms separates silence from speech', () => {
  assert.equal(rms(new Int16Array(100)), 0);
  assert.ok(rms(new Int16Array(100).fill(8000)) > 0.2);
});
