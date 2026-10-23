import assert from 'node:assert/strict';
import { test } from 'node:test';

import { debounceFor, splitForSpeech, isForMe, isSleepCommand, lifecycleAction, isLeadIn, startsWithName, isNoise, isStopCommand, voiceSummary, wantsFullReadout } from './policy.ts';

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

test('addressing by name, with likely mishearings', () => {
  const timmy = ['timmy', 'tim', 'jimmy'];
  for (const x of ['Timmy, what is the flight price?', 'Hey Timmy can you help', 'Okay, Tim: plan the trip', 'Jimmy, are you there']) assert.ok(startsWithName(x, timmy), x);
  for (const x of ['What time is it', 'Tell Timmy to wait', 'Tiff, hello', '']) assert.ok(!startsWithName(x, timmy), x);
});

test('who answers: named agent only when addressed, default agent otherwise', () => {
  const timmy = ['timmy', 'tim', 'jimmy'];
  assert.ok(isForMe('Timmy, plan Rotorua', timmy, []));
  assert.ok(!isForMe('Tiff, what is on today', timmy, []));
  assert.ok(isForMe('Tiff, what is on today', [], timmy));
  assert.ok(isForMe('What is on today', [], timmy));
  assert.ok(!isForMe('Timmy, plan Rotorua', [], timmy));
});

test('sleep commands are short and explicit', () => {
  for (const x of ['Go to sleep', 'Tiff, go to sleep.', 'stop listening', 'Mute', 'okay hang up now']) assert.ok(isSleepCommand(x), x);
  for (const x of ['I could not sleep last night and was listening to music all night', 'what is the weather', '']) assert.ok(!isSleepCommand(x), x);
});

test('lifecycle: join when George arrives, leave after he goes, rejoin if dropped', () => {
  assert.equal(lifecycleAction({ georgeInChannel: true, connected: false, leaving: false }), 'join');
  assert.equal(lifecycleAction({ georgeInChannel: true, connected: true, leaving: false }), 'none');
  assert.equal(lifecycleAction({ georgeInChannel: true, connected: true, leaving: true }), 'cancel-leave');
  assert.equal(lifecycleAction({ georgeInChannel: false, connected: true, leaving: false }), 'schedule-leave');
  assert.equal(lifecycleAction({ georgeInChannel: false, connected: true, leaving: true }), 'none');
  assert.equal(lifecycleAction({ georgeInChannel: false, connected: false, leaving: false }), 'none');
});

test('speech is split so the first sentence can start early', () => {
  const chunks = splitForSpeech('Sure thing. The flights are about seventeen hundred dollars. Cheapest is out of Sydney on Friday. Want me to hold it?');
  assert.ok(chunks.length >= 2);
  assert.equal(chunks.join(' '), 'Sure thing. The flights are about seventeen hundred dollars. Cheapest is out of Sydney on Friday. Want me to hold it?');
  assert.deepEqual(splitForSpeech('Okay.'), ['Okay.']);
  assert.ok(chunks[0].length >= 40);
});

test('debounce waits longer when the pause sounds unfinished', () => {
  assert.equal(debounceFor('Can you check my calendar for today?'), 2000);
  assert.equal(debounceFor('Right, now...'), 4500);
  assert.equal(debounceFor('Right, now'), 4000);
  assert.equal(debounceFor('So what I want to do is'), 4500);
  assert.equal(debounceFor('I need to plan the trip and,'), 4500);
  assert.equal(debounceFor('I was thinking about the trip and then'), 4500);
  assert.equal(debounceFor('I want to book the flights for the family to Rotorua for the trail race'), 3500);
  assert.equal(debounceFor(Array(26).fill('word').join(' ') + '.'), 3000);
  assert.equal(debounceFor('Yes.'), 4000);
});
