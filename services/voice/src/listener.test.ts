import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import { AddresseeState } from './addressee.ts';
import { controlPath, sendControl, serveControl, type ControlMessage } from './control.ts';
import { GateGroup } from './gate.ts';
import { routeTargets } from './router.ts';

const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), 'voice-test-'));
const NOW = 1_700_000_000_000;

test('routeTargets: a name wins, an unnamed follow-up stays with them, nobody yet means Tiff', () => {
  const state = new AddresseeState(path.join(tmp(), 'addressee.json'));
  assert.deepEqual(routeTargets([], state, NOW), ['tiff']);
  assert.deepEqual(routeTargets(['jack'], state, NOW + 1000), ['jack']);
  assert.deepEqual(routeTargets([], state, NOW + 60_000), ['jack']); // the conversation with Jack continues
  assert.deepEqual(routeTargets(['tiff', 'jimmy'], state, NOW + 90_000), ['tiff', 'jimmy']);
  assert.deepEqual(routeTargets([], state, NOW + 90_000 + 10 * 60_000), ['tiff']); // it went quiet: back to the default
});

test('GateGroup: each agent gets only what is for it, and nothing is sent while George is talking', async () => {
  const sent: string[] = [];
  const gates = new GateGroup<'tiff' | 'jack'>(['tiff', 'jack'], (k, t) => sent.push(`${k}:${t}`), 0.001);
  gates.captureStart();
  gates.transcribeStart();
  gates.captureEnd();
  gates.add(['jack'], 'research Tasmania');
  gates.transcribeEnd();
  await new Promise((r) => setTimeout(r, 30));
  assert.deepEqual(sent, ['jack:research Tasmania']);
  gates.captureStart(); // he starts again: a pending send must wait
  gates.add(['tiff', 'jack'], 'both of you listen', true);
  await new Promise((r) => setTimeout(r, 30));
  assert.equal(sent.length, 1);
  gates.transcribeStart();
  gates.captureEnd();
  gates.transcribeEnd();
  await new Promise((r) => setTimeout(r, 30));
  assert.deepEqual(sent.slice(1).sort(), ['jack:both of you listen', 'tiff:both of you listen']);
});

test('control socket: say and stop reach the speaking service; a missing service reports failure', async () => {
  const dir = tmp();
  const file = controlPath(dir, 'jack');
  const got: ControlMessage[] = [];
  const server = serveControl(file, (m) => void got.push(m));
  await new Promise((r) => server.once('listening', r));
  assert.equal(fs.statSync(file).mode & 0o777, 0o600);
  assert.equal(await sendControl(file, { op: 'say', text: 'hello Jack', clipEnd: 5 }), true);
  assert.equal(await sendControl(file, { op: 'stop' }), true);
  assert.deepEqual(got, [{ op: 'say', text: 'hello Jack', clipEnd: 5 }, { op: 'stop' }]);
  server.close();
  assert.equal(await sendControl(controlPath(dir, 'jimmy'), { op: 'stop' }), false); // nothing listening there
});

test('control socket ignores junk and unknown operations', async () => {
  const dir = tmp();
  const file = controlPath(dir, 'jimmy');
  const got: unknown[] = [];
  const server = serveControl(file, (m) => void got.push(m));
  await new Promise((r) => server.once('listening', r));
  assert.equal(await sendControl(file, { op: 'say' } as unknown as ControlMessage), true); // answered, but not handed on
  assert.equal(await sendControl(file, { op: 'reboot' } as unknown as ControlMessage), true);
  assert.deepEqual(got, []);
  server.close();
});
