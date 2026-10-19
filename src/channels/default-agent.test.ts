import { describe, expect, it } from 'vitest';

import type { InboundEvent } from './adapter.js';
import { qualifiesForDefaultAgent } from './default-agent.js';

function event(over: {
  text?: string;
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
