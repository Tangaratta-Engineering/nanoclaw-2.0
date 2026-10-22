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
 *   - it has text OR an attachment (a Discord voice message has NO text, only an audio
 *     attachment — it must not be dropped);
 *   - its author is not a bot (never react to bot posts: avoids agent loops).
 *
 * Second job: a `mention-sticky` session stays engaged with EVERY later message in its chat, so a
 * message that tags the OTHER agent (and not this one) would still reach this agent's session. Such
 * messages are consumed here so each agent only reacts to what is meant for it.
 */
import { readEnvFile } from '../env.js';
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
  let parsed: { text?: unknown; attachments?: unknown; author?: { isBot?: unknown } };
  try {
    parsed = JSON.parse(event.message.content);
  } catch {
    return false;
  }
  if (parsed.author?.isBot === true) return false;
  const text = typeof parsed.text === 'string' ? parsed.text : '';
  const hasAttachments = Array.isArray(parsed.attachments) && parsed.attachments.length > 0;
  if (text.trim().length === 0 && !hasAttachments) return false;
  if (text.includes('<@')) return false;
  return true;
}

/** Discord ids (bot user + mention roles) that address each agent, by adapter instance. */
type AgentIds = Record<string, string[]>;

let cachedIds: AgentIds | null = null;
function agentIds(): AgentIds {
  if (cachedIds) return cachedIds;
  const env = readEnvFile(['DISCORD_APPLICATION_ID', 'DISCORD_MENTION_ROLE_IDS', 'DISCORD_TIMMY_APPLICATION_ID', 'DISCORD_TIMMY_MENTION_ROLE_IDS']);
  const list = (app?: string, roles?: string) => [app, ...(roles ?? '').split(',')].map((x) => (x ?? '').trim()).filter(Boolean);
  cachedIds = {
    discord: list(env.DISCORD_APPLICATION_ID, env.DISCORD_MENTION_ROLE_IDS),
    timmy: list(env.DISCORD_TIMMY_APPLICATION_ID, env.DISCORD_TIMMY_MENTION_ROLE_IDS),
  };
  return cachedIds;
}

/**
 * Pure decision: is this group message addressed to a different agent than the instance receiving it
 * (it tags that agent's bot or role, and does not tag this one)?
 */
export function addressedToOtherAgent(event: InboundEvent, ids: AgentIds): boolean {
  if (event.channelType !== 'discord' || event.message.kind !== 'chat-sdk') return false;
  if (event.message.isMention === true || event.message.isGroup !== true) return false;
  const instance = event.instance ?? event.channelType;
  if (!ids[instance]) return false;
  let text = '';
  try {
    const parsed = JSON.parse(event.message.content) as { text?: unknown };
    text = typeof parsed.text === 'string' ? parsed.text : '';
  } catch {
    return false;
  }
  const tagged = new Set([...text.matchAll(/<@&?(\d+)>/g)].map((m) => m[1]));
  if (ids[instance].some((id) => tagged.has(id))) return false; // tags this agent too
  return Object.entries(ids).some(([name, list]) => name !== instance && list.some((id) => tagged.has(id)));
}

registerMessageInterceptor(async (event) => {
  if (addressedToOtherAgent(event, agentIds())) return true; // not for this agent: consume it
  if (!qualifiesForDefaultAgent(event)) return false;
  // Only chats that actually have an agent wired (no auto-creation for stray channels).
  const found = getMessagingGroupWithAgentCount(event.channelType, event.platformId, DEFAULT_INSTANCE);
  if (!found || found.agentCount === 0) return false;
  // Re-enter routing as a mention. The re-injected event is isMention=true, so this
  // interceptor passes on it and normal routing takes over.
  await routeInbound({ ...event, message: { ...event.message, isMention: true } });
  return true;
});
