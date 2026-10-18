/**
 * Discord channel adapter (v2) — uses Chat SDK bridge.
 * Self-registers on import.
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

/**
 * Discord autocompletes a bot's name as either the bot user or its managed
 * role of the same name; a role mention only reaches the bot when its role id
 * is listed here (comma-separated). Unset ⇒ role mentions are ignored.
 */
function parseRoleIds(raw: string | undefined): string[] | undefined {
  const ids = (raw ?? '')
    .split(',')
    .map((id) => id.trim())
    .filter(Boolean);
  return ids.length > 0 ? ids : undefined;
}

registerChannelAdapter('discord', {
  factory: () => {
    const env = readEnvFile([
      'DISCORD_BOT_TOKEN',
      'DISCORD_PUBLIC_KEY',
      'DISCORD_APPLICATION_ID',
      'DISCORD_MENTION_ROLE_IDS',
    ]);
    if (!env.DISCORD_BOT_TOKEN) return null;
    const discordAdapter = createDiscordAdapter({
      botToken: env.DISCORD_BOT_TOKEN,
      publicKey: env.DISCORD_PUBLIC_KEY,
      applicationId: env.DISCORD_APPLICATION_ID,
      mentionRoleIds: parseRoleIds(env.DISCORD_MENTION_ROLE_IDS),
    });
    return createChatSdkBridge({
      adapter: discordAdapter,
      concurrency: 'concurrent',
      botToken: env.DISCORD_BOT_TOKEN,
      extractReplyContext,
      supportsThreads: true,
    });
  },
});

// Optional second Discord bot (own identity/DM), keyed as instance "timmy".
// Absent DISCORD_TIMMY_* vars ⇒ not registered; the default bot is unaffected.
registerChannelAdapter('discord-timmy', {
  factory: () => {
    const env = readEnvFile([
      'DISCORD_TIMMY_BOT_TOKEN',
      'DISCORD_TIMMY_PUBLIC_KEY',
      'DISCORD_TIMMY_APPLICATION_ID',
      'DISCORD_TIMMY_MENTION_ROLE_IDS',
    ]);
    if (!env.DISCORD_TIMMY_BOT_TOKEN) return null;
    const discordAdapter = createDiscordAdapter({
      botToken: env.DISCORD_TIMMY_BOT_TOKEN,
      publicKey: env.DISCORD_TIMMY_PUBLIC_KEY,
      applicationId: env.DISCORD_TIMMY_APPLICATION_ID,
      mentionRoleIds: parseRoleIds(env.DISCORD_TIMMY_MENTION_ROLE_IDS),
    });
    return createChatSdkBridge({
      adapter: discordAdapter,
      instance: 'timmy',
      concurrency: 'concurrent',
      botToken: env.DISCORD_TIMMY_BOT_TOKEN,
      extractReplyContext,
      supportsThreads: true,
    });
  },
});
