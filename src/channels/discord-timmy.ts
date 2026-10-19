/**
 * LOCAL CUSTOMIZATION (not part of upstream NanoClaw) — see docs/local-customizations.md.
 *
 * Adds a second Discord bot with its own identity, registered as adapter
 * instance "timmy", and makes both bots react to Discord *role* mentions.
 *
 * Lives in its own file on purpose: discord.ts is installed from the
 * `channels` branch by /add-discord and re-copied by /update-skills, so edits
 * there would be silently overwritten on upgrade. This file only needs the
 * one-line barrel import in index.ts.
 *
 * Env (all optional; absent ⇒ nothing registered / no change):
 *   DISCORD_TIMMY_BOT_TOKEN, DISCORD_TIMMY_PUBLIC_KEY, DISCORD_TIMMY_APPLICATION_ID
 *   DISCORD_TIMMY_MENTION_ROLE_IDS   comma-separated role ids that count as @mentions of this bot
 *   DISCORD_MENTION_ROLE_IDS         same, for the default bot (read by the adapter from process.env)
 *
 * Why role mentions: Discord autocompletes a bot's name as either the bot user
 * or its managed role of the same name. The adapter ignores role mentions
 * unless the role id is configured, so they were silently dropped.
 */
import { createDiscordAdapter } from '@chat-adapter/discord';

import { readEnvFile } from '../env.js';
import { createChatSdkBridge, type ReplyContext } from './chat-sdk-bridge.js';
import { registerChannelAdapter } from './channel-registry.js';

// The default bot's adapter reads DISCORD_MENTION_ROLE_IDS from process.env in
// its constructor (not from .env, which this codebase deliberately keeps out
// of process.env). Role ids are not secrets, so bridge just this one value.
// Runs at import time, before any adapter factory executes at startup.
const defaultRoles = readEnvFile(['DISCORD_MENTION_ROLE_IDS']).DISCORD_MENTION_ROLE_IDS;
if (defaultRoles && !process.env.DISCORD_MENTION_ROLE_IDS) {
  process.env.DISCORD_MENTION_ROLE_IDS = defaultRoles;
}

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
