import { describe, expect, it } from 'vitest';

import type { InboundEvent } from './adapter.js';
import { addressedToOtherAgent, qualifiesForDefaultAgent } from './default-agent.js';

function event(over: {
  text?: string;
  attachments?: unknown[];
  isBot?: boolean;
  threadId?: string | null;
  isMention?: boolean;
  isGroup?: boolean;
  instance?: string;
  channelType?: string;
  kind?: 'chat' | 'chat-sdk';
}): InboundEvent {
  const base = 'discord:111:222';
  return {
    channelType: over.channelType ?? 'discord',
    instance: over.instance ?? 'discord',
    platformId: base,
    threadId: over.threadId === undefined ? base : over.threadId,
    message: {
      id: 'm1',
      kind: over.kind ?? 'chat-sdk',
      timestamp: new Date().toISOString(),
      isMention: over.isMention ?? false,
      isGroup: over.isGroup ?? true,
      content: JSON.stringify({
        text: over.text ?? 'what is on my calendar today?',
        attachments: over.attachments,
        author: { userId: 'u1', isBot: over.isBot ?? false },
      }),
    },
  };
}

describe('qualifiesForDefaultAgent', () => {
  it('claims a plain channel-level message with no handle', () => {
    expect(qualifiesForDefaultAgent(event({}))).toBe(true);
    expect(qualifiesForDefaultAgent(event({ threadId: null }))).toBe(true);
  });

  it('claims an attachment-only message (a Discord voice message has no text)', () => {
    const voice = { type: 'audio', name: 'voice-message.ogg', mimeType: 'audio/ogg' };
    expect(qualifiesForDefaultAgent(event({ text: '', attachments: [voice] }))).toBe(true);
    expect(qualifiesForDefaultAgent(event({ text: '   ', attachments: [voice], threadId: null }))).toBe(true);
  });

  it('still ignores a message with neither text nor attachments, and attachment messages that are addressed or in threads', () => {
    expect(qualifiesForDefaultAgent(event({ text: '', attachments: [] }))).toBe(false);
    expect(qualifiesForDefaultAgent(event({ text: '<@999>', attachments: [{ type: 'audio' }] }))).toBe(false);
    expect(
      qualifiesForDefaultAgent(event({ text: '', attachments: [{ type: 'audio' }], threadId: 'discord:1:2:3' })),
    ).toBe(false);
    expect(qualifiesForDefaultAgent(event({ text: '', attachments: [{ type: 'audio' }], isBot: true }))).toBe(false);
  });

  it('leaves messages that already mention the bot to normal routing', () => {
    expect(qualifiesForDefaultAgent(event({ isMention: true }))).toBe(false);
  });

  it('never claims messages addressed to anyone else (user or role mention)', () => {
    expect(qualifiesForDefaultAgent(event({ text: '<@999> hello' }))).toBe(false);
    expect(qualifiesForDefaultAgent(event({ text: 'hey <@&888> can you plan this' }))).toBe(false);
  });

  it('never claims messages inside a thread (threads belong to the agent mentioned there)', () => {
    expect(qualifiesForDefaultAgent(event({ threadId: 'discord:111:222:333' }))).toBe(false);
  });

  it('never claims bot-authored messages (prevents agent-to-agent loops)', () => {
    expect(qualifiesForDefaultAgent(event({ isBot: true }))).toBe(false);
  });

  it('ignores other instances, other channels, DMs, empty text and non-chat kinds', () => {
    expect(qualifiesForDefaultAgent(event({ instance: 'timmy' }))).toBe(false);
    expect(qualifiesForDefaultAgent(event({ channelType: 'telegram' }))).toBe(false);
    expect(qualifiesForDefaultAgent(event({ isGroup: false }))).toBe(false);
    expect(qualifiesForDefaultAgent(event({ text: '   ' }))).toBe(false);
    expect(qualifiesForDefaultAgent(event({ kind: 'chat' }))).toBe(false);
  });
});

describe('addressedToOtherAgent', () => {
  const ids = { discord: ['100', '101'], timmy: ['200', '201'] };

  it("consumes a message that tags only the other agent's bot or role", () => {
    expect(addressedToOtherAgent(event({ text: 'plan the trip <@200>' }), ids)).toBe(true);
    expect(addressedToOtherAgent(event({ text: '<@&201> plan the trip' }), ids)).toBe(true);
    expect(addressedToOtherAgent(event({ text: '<@100> hi', instance: 'timmy' }), ids)).toBe(true); // symmetric
  });

  it('lets through messages that also tag this agent, or tag nobody, or tag a human', () => {
    expect(addressedToOtherAgent(event({ text: '<@100> and <@200> meet' }), ids)).toBe(false);
    expect(addressedToOtherAgent(event({ text: 'what is on today' }), ids)).toBe(false);
    expect(addressedToOtherAgent(event({ text: '<@999> dinner?' }), ids)).toBe(false);
  });

  it('ignores direct messages, other channel types and already-mentions', () => {
    expect(addressedToOtherAgent(event({ text: '<@200> hi', isGroup: false }), ids)).toBe(false);
    expect(addressedToOtherAgent(event({ text: '<@200> hi', isMention: true }), ids)).toBe(false);
    expect(addressedToOtherAgent(event({ text: '<@200> hi', channelType: 'telegram' }), ids)).toBe(false);
  });
});
