import { describe, expect, it } from 'vitest';

import { DiscordAdapter } from '@chat-adapter/discord';

import { disableDiscordThreads } from './no-discord-threads.js';

describe('disableDiscordThreads', () => {
  it('makes the Discord adapter report no thread, so replies stay in the channel', async () => {
    class Fake {
      async createDiscordThread(): Promise<{ id: string }> {
        return { id: 'thread-1' };
      }
    }
    const before = await new Fake().createDiscordThread();
    expect(before.id).toBe('thread-1');
    disableDiscordThreads(Fake);
    const after = await (
      new Fake() as unknown as { createDiscordThread: () => Promise<{ id?: string }> }
    ).createDiscordThread();
    expect(after.id).toBeUndefined();
  });

  it('is applied to the real adapter class on import', async () => {
    await import('./no-discord-threads.js');
    const result = await (
      DiscordAdapter.prototype as unknown as { createDiscordThread: () => Promise<{ id?: string }> }
    ).createDiscordThread();
    expect(result.id).toBeUndefined();
  });
});
