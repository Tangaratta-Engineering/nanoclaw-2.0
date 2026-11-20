import test from 'node:test';
import assert from 'node:assert/strict';

import { ClipVad, DEFAULT_VAD, NoiseFloor, frameRms, pcmMs } from './vad.ts';

const run = (vad: ClipVad, levels: number[], ms = 20): string[] => levels.map((l) => vad.push(l, ms));
const times = (n: number, v: number) => Array<number>(n).fill(v);

test('speech then quiet ends the clip after the silence window, even though audio keeps arriving', () => {
  const vad = new ClipVad(DEFAULT_VAD, new NoiseFloor(0.004));
  const ev = run(vad, [...times(50, 0.05), ...times(80, 0.006)]); // 1 s of speech, then 1.6 s of steady noise
  assert.ok(ev.includes('speech-start'));
  assert.equal(ev.indexOf('end-speech'), 50 + 65 - 1); // 1300 ms of quiet = 65 frames
});

test('pauses inside a sentence do not end it', () => {
  const vad = new ClipVad(DEFAULT_VAD, new NoiseFloor(0.004));
  const ev = run(vad, [...times(40, 0.05), ...times(40, 0.005), ...times(40, 0.05), ...times(40, 0.005)]); // 800 ms pauses
  assert.ok(!ev.slice(0, 120).includes('end-speech'));
});

test('a clip of only background noise is dropped, and never counts as speech', () => {
  const vad = new ClipVad(DEFAULT_VAD, new NoiseFloor(0.004));
  const ev = run(vad, times(100, 0.008));
  assert.ok(ev.includes('end-noise'));
  assert.ok(!ev.includes('speech-start'));
  assert.equal(vad.isSpeech, false);
});

test('a short click or cough is not speech', () => {
  const vad = new ClipVad(DEFAULT_VAD, new NoiseFloor(0.004));
  const ev = run(vad, [...times(5, 0.2), ...times(80, 0.005)]); // 100 ms spike
  assert.ok(!ev.includes('speech-start'));
  assert.ok(ev.includes('end-noise'));
});

test('steady loud noise is learned as the background: speech still stands out above it', () => {
  const floor = new NoiseFloor(0.004);
  for (let i = 0; i < 1500; i++) floor.update(0.02); // 30 s of car noise
  assert.ok(floor.value > 0.01);
  const noiseOnly = run(new ClipVad(DEFAULT_VAD, floor), times(100, 0.02));
  assert.ok(noiseOnly.includes('end-noise') && !noiseOnly.includes('speech-start'));
  const ev = run(new ClipVad(DEFAULT_VAD, floor), [...times(30, 0.12), ...times(80, 0.02)]);
  assert.ok(ev.includes('speech-start') && ev.includes('end-speech'));
});

test('a clip never runs longer than the maximum', () => {
  const vad = new ClipVad({ ...DEFAULT_VAD, maxClipMs: 2000 }, new NoiseFloor(0.004));
  const ev = run(vad, times(200, 0.05));
  assert.equal(ev.indexOf('end-speech'), 99);
});

test('frameRms and pcmMs read 48 kHz stereo s16le', () => {
  const b = Buffer.alloc(3840);
  assert.equal(frameRms(b), 0);
  assert.equal(pcmMs(b), 20);
  for (let i = 0; i < b.length / 2; i++) b.writeInt16LE(16384, i * 2);
  assert.ok(Math.abs(frameRms(b) - 0.5) < 0.001);
});
