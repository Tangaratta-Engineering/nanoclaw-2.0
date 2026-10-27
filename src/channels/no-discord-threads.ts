/**
 * LOCAL CUSTOMIZATION (not part of upstream NanoClaw) — see docs/local-customizations.md.
 *
 * Keep Discord conversations in the channel instead of spawning a thread per mention.
 *
 * `@chat-adapter/discord` creates a Discord thread from every message that mentions the bot (hard-coded,
 * no option), which scatters one conversation across many threads. Its `createDiscordThread` is only
 * called to obtain a thread id; if the id comes back undefined the adapter falls back to the channel
 * itself, so replies post in the channel. Both Discord bots (Tiff and Timmy) share this class.
 *
 * Set `DISCORD_THREADS=on` to get the stock behaviour back.
 */
import { DiscordAdapter } from '@chat-adapter/discord';

type ThreadResult = { id: string | undefined; name: string };

export function disableDiscordThreads(adapterClass: { prototype: object } = DiscordAdapter): void {
  (adapterClass.prototype as { createDiscordThread: () => Promise<ThreadResult> }).createDiscordThread = async () => ({
    id: undefined,
    name: '',
  });
}

if (process.env.DISCORD_THREADS !== 'on') disableDiscordThreads();
