import net from 'node:net';

import type { Config } from './config.ts';

const PREAMBLE =
  '[LIVE VOICE CALL — your reply will be spoken aloud in real time. Answer in one to three short, plain sentences: no markdown, lists, emoji or links. If the task needs more than a quick answer, say what you are doing in one sentence, do it, then speak a one-sentence result and send the details as a normal text message to George.]\n';

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
