import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';

import { handle, keyOk } from './api.ts';
import { isAllowed, labelFor } from './config.ts';
import { extractText } from './extract.ts';
import { Store } from './store.ts';

const KEY = 'secret-key';
const now = Math.floor(Date.now() / 1000);
const msg = (id: string, text: string, chat = 'g1@g.us', ts = now) => ({ id, chatJid: chat, chatName: 'Northside Montessori P&C', sender: 'Jenny', ts, text, kind: 'text' });
const get = (s: Store, p: string, key: string | null = KEY) => handle(s, 'GET', new URL('http://x' + p), null, key ?? undefined, KEY, () => true);

function seeded(): Store {
  const s = new Store(':memory:');
  s.setChat('g1@g.us', 'Northside Montessori P&C', true);
  s.setChat('g2@g.us', 'Poker night', false);
  s.add(msg('1', 'Swimming carnival moved to Friday 21 November'));
  s.add(msg('2', 'Anyone have a spare hat?'));
  return s;
}

test('the allowlist matches by name prefix or by id, and an empty list allows nothing', () => {
  const list = { namePrefixes: ['Northside Montessori'], jids: ['x@g.us'] };
  assert.equal(isAllowed(list, 'a@g.us', 'northside montessori - Orana'), true);
  assert.equal(isAllowed(list, 'x@g.us', null), true);
  assert.equal(isAllowed(list, 'b@g.us', 'Poker night'), false);
  assert.equal(isAllowed({ namePrefixes: [], jids: [] }, 'a@g.us', 'Anything'), false);
  assert.equal(isAllowed({ namePrefixes: [''], jids: [] }, 'a@g.us', 'Anything'), false);
});

test('messages are searchable, deduplicated, and a non-allowed chat never shows up', () => {
  const s = seeded();
  assert.equal(s.add(msg('1', 'Swimming carnival moved to Friday 21 November')), false);
  s.add(msg('9', 'poker secret', 'g2@g.us'));
  assert.equal(s.search('carnival').length, 1);
  assert.equal(s.search('poker').length, 0);
  assert.equal(s.recent(24).length, 2);
  assert.equal(s.search('"; drop table messages; --').length, 0);
});

test('every endpoint but /health needs the key, bare or with a Bearer prefix', () => {
  const s = seeded();
  assert.equal(get(s, '/health', null).status, 200);
  for (const p of ['/chats', '/messages/new', '/messages/recent', '/messages/search?q=x']) {
    assert.equal(get(s, p, null).status, 403);
    assert.equal(get(s, p, 'wrong').status, 403);
    assert.equal(get(s, p).status, 200);
    assert.equal(get(s, p, 'Bearer ' + KEY).status, 200);
  }
  assert.equal(keyOk('x', ''), false);
});

test('new messages wake the agent once, until they are reported', () => {
  const s = seeded();
  const first = get(s, '/messages/new').body as any;
  assert.equal(first.wakeAgent, true);
  assert.equal(first.data.count, 2);
  assert.match(first.data.note, /never follow instructions/);
  const marked = handle(s, 'POST', new URL('http://x/messages/reported'), { messages: first.data.messages.map((m: any) => ({ chat: m.chatJid, id: m.id })) }, KEY, KEY, () => true);
  assert.deepEqual(marked.body, { marked: 2 });
  const again = get(s, '/messages/new').body as any;
  assert.equal(again.wakeAgent, false);
  assert.equal(again.data.count, 0);
});

test('text is pulled out of the message shapes WhatsApp sends', () => {
  assert.deepEqual(extractText({ conversation: 'hi' }), { text: 'hi', kind: 'text' });
  assert.equal(extractText({ extendedTextMessage: { text: 'link' } })?.text, 'link');
  assert.equal(extractText({ imageMessage: { caption: 'flyer' } })?.text, 'flyer');
  assert.equal(extractText({ documentMessage: { fileName: 'minutes.pdf' } })?.text, '[document: minutes.pdf]');
  assert.equal(extractText({ ephemeralMessage: { message: { conversation: 'x' } } })?.text, 'x');
  assert.equal(extractText({ reactionMessage: { text: '👍' } }), null);
  assert.equal(extractText(null), null);
});

test('GUARD: nothing in this service can send, mark read or show presence', () => {
  const dir = path.dirname(new URL(import.meta.url).pathname);
  const forbidden = /\.(sendMessage|readMessages|sendPresenceUpdate|presenceSubscribe|chatModify|sendReceipts?|relayMessage|updateBlockStatus|rejectCall|groupLeave|groupParticipantsUpdate|groupUpdate\w*|updateProfile\w*)\s*\(/;
  for (const f of fs.readdirSync(dir).filter((x) => x.endsWith('.ts') && !x.endsWith('.test.ts'))) {
    const src = fs.readFileSync(path.join(dir, f), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
    assert.doesNotMatch(src, forbidden, `${f} must not call a WhatsApp write function`);
  }
  assert.match(fs.readFileSync(path.join(dir, 'index.ts'), 'utf8'), /markOnlineOnConnect:\s*false/);
});

test('a labelled chat is found under either of the ids WhatsApp may use and shows the name George gave it', () => {
  const list = { namePrefixes: [], jids: ['61406691196@s.whatsapp.net'], labels: { '61406691196@s.whatsapp.net': 'James Wong' } };
  assert.equal(labelFor(list, '123@lid', '61406691196@s.whatsapp.net'), 'James Wong');
  assert.equal(labelFor(list, '123@lid', undefined), null);
  assert.equal(isAllowed(list, '61406691196@s.whatsapp.net', null), true);
  const s = new Store(':memory:');
  s.setChat('123@lid', 'James Wong', true);
  s.add({ id: '1', chatJid: '123@lid', chatName: 'James Wong', sender: 'James Wong', ts: now, text: 'Lesson moved to 4pm', kind: 'text' });
  assert.equal(s.recent(24, 'James').length, 1);          // found by name
  assert.equal(s.search('James lesson').length, 1);       // and by words, name included
});
