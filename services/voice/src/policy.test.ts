import assert from 'node:assert/strict';
import { test } from 'node:test';

import { isLeadIn, isNoise, isStopCommand, voiceSummary, wantsFullReadout } from './policy.ts';

test('stop words only when short', () => {
  for (const t of ['Stop.', 'Stop talking', 'Hold on', 'wait', 'OK stop!', 'Tiff, stop']) assert.ok(isStopCommand(t), t);
  for (const t of ['Can you stop by the shops later', 'What time does the bus stop open', 'continue', '']) assert.ok(!isStopCommand(t), t);
});

test('noise rules differ while she is speaking', () => {
  assert.ok(isNoise('', 'good', false));
  assert.ok(isNoise('Thank you.', 'good', false));
  assert.ok(!isNoise('Continue.', 'good', false));
  assert.ok(isNoise('Continue.', 'good', true)); // one word while she talks: ignore
  assert.ok(isNoise('what about the tents', 'uncertain', true));
  assert.ok(!isNoise('what about the tents', 'good', true));
});

test('summary keeps it short and points to chat', () => {
  assert.equal(voiceSummary('Short reply.'), 'Short reply.');
  const long = 'First sentence is here. Second sentence follows. ' + 'More words. '.repeat(60);
  const s = voiceSummary(long);
  assert.ok(s.length < 330);
  assert.ok(s.endsWith('The rest is in the chat.'));
  assert.ok(s.startsWith('First sentence is here.'));
});

test('whisper hallucinations are noise', () => {
  for (const x of ['Subtitles by the Amara.org community', 'Thanks for watching!', 'Please subscribe']) assert.ok(isNoise(x, 'uncertain', false), x);
});

test('code spans are not spoken; lead-ins and read-outs recognised', () => {
  assert.equal(voiceSummary('Added to `/workspace/agent/x.md` today.'), 'Added to today.');
  assert.ok(isLeadIn('Costume jobs added to the file, at the top:'));
  assert.ok(!isLeadIn('All done.'));
  assert.ok(wantsFullReadout('Can you read that list back to me?'));
  assert.ok(!wantsFullReadout('what is six times six'));
});
