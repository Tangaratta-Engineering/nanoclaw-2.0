import assert from 'node:assert/strict';
import { test, mock } from 'node:test';

import { SendGate } from './gate.ts';

function setup() {
  mock.timers.enable({ apis: ['setTimeout'] });
  const sent: string[] = [];
  return { sent, gate: new SendGate((t) => sent.push(t)) };
}

test('a finished sentence is sent after its wait, not before', () => {
  const { sent, gate } = setup();
  gate.transcribeStart(); gate.captureStart(); gate.captureEnd();
  gate.add('Can you check my calendar for today?'); gate.transcribeEnd();
  mock.timers.tick(1900); assert.deepEqual(sent, []);
  mock.timers.tick(200); assert.deepEqual(sent, ['Can you check my calendar for today?']);
  mock.timers.reset();
});

test('a pause that sounds unfinished waits longer ("Right, now...")', () => {
  const { sent, gate } = setup();
  gate.captureStart(); gate.transcribeStart(); gate.captureEnd();
  gate.add('Right, now...'); gate.transcribeEnd();
  mock.timers.tick(4000); assert.deepEqual(sent, []);
  mock.timers.tick(600); assert.deepEqual(sent, ['Right, now...']);
  mock.timers.reset();
});

test('resuming speech cancels the pending send, and the two parts go out as one message', () => {
  const { sent, gate } = setup();
  gate.captureStart(); gate.transcribeStart(); gate.captureEnd();
  gate.add('Right, now...'); gate.transcribeEnd();
  mock.timers.tick(3000);
  gate.captureStart(); // he starts talking again before the timer fires
  mock.timers.tick(10_000); assert.deepEqual(sent, []); // however long he talks, nothing is sent
  gate.transcribeStart(); gate.captureEnd();
  mock.timers.tick(10_000); assert.deepEqual(sent, []); // still transcribing
  gate.add('The next log I want you to put is for Norflex.'); gate.transcribeEnd();
  mock.timers.tick(2100);
  assert.deepEqual(sent, ['Right, now... The next log I want you to put is for Norflex.']);
  mock.timers.reset();
});

test('a filler or breath while composing extends the wait', () => {
  const { sent, gate } = setup();
  gate.captureStart(); gate.transcribeStart(); gate.captureEnd();
  gate.add('I need to book the flights.'); gate.transcribeEnd(); // 2000 ms wait
  mock.timers.tick(1500);
  gate.captureStart(); gate.transcribeStart(); gate.captureEnd(); gate.filler(); gate.transcribeEnd(); // "um"
  mock.timers.tick(2900); assert.deepEqual(sent, []);
  mock.timers.tick(200); assert.deepEqual(sent, ['I need to book the flights.']);
  mock.timers.reset();
});

test('reset drops the buffer and a stuck capture counter', () => {
  const { sent, gate } = setup();
  gate.captureStart(); gate.reset();
  gate.transcribeStart(); gate.add('This is a complete sentence after the reset.'); gate.transcribeEnd();
  mock.timers.tick(2100); assert.deepEqual(sent, ['This is a complete sentence after the reset.']);
  mock.timers.reset();
});
