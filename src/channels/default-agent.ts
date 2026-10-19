/**
 * LOCAL CUSTOMIZATION (not part of upstream NanoClaw) — see docs/local-customizations.md.
 *
 * "Default agent" for a shared Discord server channel: a message with no @handle
 * at all is managed by the default bot's agent (Tiff), which then answers it or
 * hands it to the other agent per its delegation rules. Without this, a wiring in
 * `mention` / `mention-sticky` mode silently drops anything that does not mention
 * the bot.
 *
 * Implemented as a pre-route interceptor that re-injects qualifying messages as
 * mentions of the default bot, so the router and the wiring (keep it
 * `mention-sticky`) need no changes. A message qualifies only when ALL hold:
 *   - it arrived on the default Discord instance, in a group channel that is wired;
 *   - it is not already a mention of the bot;
 *   - it is at channel level — NOT inside a thread (threads belong to whichever
 *     agent was mentioned there; the other bot's threads must stay its own);
 *   - its text contains no Discord mention at all (`<@…>` / `<@&…>`) — so anything
 *     addressed to another bot, by user or role mention, is left to that bot;
 *   - its author is not a bot (never react to bot posts: avoids agent loops).
 */
import { getMessagingGroupWithAgentCount } from '../db/messaging-groups.js';
import { registerMessageInterceptor, routeInbound } from '../router.js';
import type { InboundEvent } from './adapter.js';

const DEFAULT_INSTANCE = 'discord';

/** Discord thread ids: `discord:<guild>:<channel>` at channel level, one more part inside a thread. */
function isChannelLevel(threadId: string | null): boolean {
  return threadId === null || threadId.split(':').length <= 3;
}

/** Pure decision (no DB): should this event be re-injected as an addressed message? */
export function qualifiesForDefaultAgent(event: InboundEvent): boolean {
  if (event.channelType !== 'discord') return false;
  if ((event.instance ?? event.channelType) !== DEFAULT_INSTANCE) return false;
  if (event.message.kind !== 'chat-sdk') return false;
  if (event.message.isMention === true) return false;
  if (event.message.isGroup !== true) return false;
  if (!isChannelLevel(event.threadId)) return false;
  let parsed: { text?: unknown; author?: { isBot?: unknown } };
  try {
    parsed = JSON.parse(event.message.content);
  } catch {
    return false;
  }
  if (parsed.author?.isBot === true) return false;
  const text = typeof parsed.text === 'string' ? parsed.text : '';
  if (text.trim().length === 0) return false;
  if (text.includes('<@')) return false;
  return true;
}

registerMessageInterceptor(async (event) => {
  if (!qualifiesForDefaultAgent(event)) return false;
  // Only chats that actually have an agent wired (no auto-creation for stray channels).
  const found = getMessagingGroupWithAgentCount(event.channelType, event.platformId, DEFAULT_INSTANCE);
  if (!found || found.agentCount === 0) return false;
  // Re-enter routing as a mention. The re-injected event is isMention=true, so this
  // interceptor passes on it and normal routing takes over.
  await routeInbound({ ...event, message: { ...event.message, isMention: true } });
  return true;
});
