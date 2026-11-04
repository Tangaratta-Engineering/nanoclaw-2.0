import net from 'node:net';

import type { Config } from './config.ts';

const PREAMBLE =
  '[LIVE VOICE CALL — your reply will be spoken aloud in real time. Send ONE reply message. Match its length to the question: a quick fact, confirmation or yes/no gets one or two sentences; when George asks you to explain, compare, plan, recommend or walk through something, give a proper spoken answer of as many sentences as it needs (up to about a minute of speech), reasoning included, not a one-line summary. ONE exception: if answering needs research or tool work that will take more than a few seconds, FIRST send a short spoken acknowledgement of at most eight words as its own message (for example "Looking into that now."), then do the work, then send the answer as your second and last spoken message. Speak in natural flowing sentences: no markdown, lists, emoji, links, file paths or progress notes, and say numbers the way you would aloud. Put exact figures, links and long lists in a separate text message that starts with the word DETAILS. If George asks you to read something out, read it in full in that one message.]\n';

/** Send a transcript into the agent's DM session through the host's CLI socket (one short connection per message). */
export function sendToAgent(cfg: Config, transcript: string): Promise<boolean> {
  return new Promise((resolve) => {
    const s = net.createConnection(cfg.socketPath);
    s.on('error', () => resolve(false));
    s.on('connect', () => {
      s.end(
        JSON.stringify({
          text: PREAMBLE + transcript,
          to: { channelType: 'discord', platformId: cfg.dmPlatformId, threadId: null, ...(cfg.instance ? { instance: cfg.instance } : {}) },
          sender: 'George',
          senderId: `discord:${cfg.userId}`,
        }) + '\n',
        () => resolve(true),
      );
    });
  });
}
