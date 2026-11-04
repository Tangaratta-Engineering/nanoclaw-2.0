/**
 * LOCAL CUSTOMIZATION (not part of upstream NanoClaw) — see docs/local-customizations.md.
 *
 * Adds a third Discord bot with its own identity, registered as adapter
 * instance "jack" (same pattern as discord-timmy.ts). Registers nothing unless
 * DISCORD_JACK_BOT_TOKEN is set, so it is inert until George creates the bot.
 *
 * Env (all optional):
 *   DISCORD_JACK_BOT_TOKEN, DISCORD_JACK_PUBLIC_KEY, DISCORD_JACK_APPLICATION_ID
 *   DISCORD_JACK_MENTION_ROLE_IDS   comma-separated role ids that count as @mentions of this bot
 */
import { createDiscordAdapter } from '@chat-adapter/discord';

import { readEnvFile } from '../env.js';
import { createChatSdkBridge, type ReplyContext } from './chat-sdk-bridge.js';
import { registerChannelAdapter } from './channel-registry.js';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function extractReplyContext(raw: Record<string, any>): ReplyContext | null {
  if (!raw.referenced_message) return null;
  const reply = raw.referenced_message;
  return {
    text: reply.content || '',
    sender: reply.author?.global_name || reply.author?.username || 'Unknown',
  };
}

function parseRoleIds(raw: string | undefined): string[] | undefined {
  const ids = (raw ?? '')
    .split(',')
    .map((id) => id.trim())
    .filter(Boolean);
  return ids.length > 0 ? ids : undefined;
}

registerChannelAdapter('discord-jack', {
  factory: () => {
    const env = readEnvFile([
      'DISCORD_JACK_BOT_TOKEN',
      'DISCORD_JACK_PUBLIC_KEY',
      'DISCORD_JACK_APPLICATION_ID',
      'DISCORD_JACK_MENTION_ROLE_IDS',
    ]);
    if (!env.DISCORD_JACK_BOT_TOKEN) return null;
    const discordAdapter = createDiscordAdapter({
      botToken: env.DISCORD_JACK_BOT_TOKEN,
      publicKey: env.DISCORD_JACK_PUBLIC_KEY,
      applicationId: env.DISCORD_JACK_APPLICATION_ID,
      mentionRoleIds: parseRoleIds(env.DISCORD_JACK_MENTION_ROLE_IDS),
    });
    return createChatSdkBridge({
      adapter: discordAdapter,
      instance: 'jack',
      concurrency: 'concurrent',
      botToken: env.DISCORD_JACK_BOT_TOKEN,
      extractReplyContext,
      supportsThreads: true,
    });
  },
});
