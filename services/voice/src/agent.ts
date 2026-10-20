import net from 'node:net';

import type { Config } from './config.ts';

const PREAMBLE =
  '[LIVE VOICE CALL — your reply will be spoken aloud in real time. Answer in one to three short, plain sentences: no markdown, lists, emoji or links. If the task needs more than a quick answer, say what you are doing in one sentence, do it, then speak a one-sentence result and send the details as a normal text message to George.]\n';

/** Client for the host's CLI socket: sends a message into the agent's DM and receives its replies. */
export class AgentLink {
  private sock: net.Socket | null = null;
  private buf = '';
  private closed = false;
  onReply: (text: string) => void = () => {};

  private cfg: Config;

  constructor(cfg: Config) {
    this.cfg = cfg;
  }

  connect(): void {
    if (this.closed) return;
    const s = net.createConnection(this.cfg.socketPath);
    this.sock = s;
    s.on('connect', () => s.write(JSON.stringify({ subscribe: true }) + '\n'));
    s.on('data', (d) => this.onData(d.toString('utf8')));
    s.on('error', () => {});
    s.on('close', () => {
      this.sock = null;
      if (!this.closed) setTimeout(() => this.connect(), 3000);
    });
  }

  private onData(chunk: string): void {
    this.buf += chunk;
    let i: number;
    while ((i = this.buf.indexOf('\n')) >= 0) {
      const line = this.buf.slice(0, i);
      this.buf = this.buf.slice(i + 1);
      try {
        const { text } = JSON.parse(line) as { text?: string };
        if (typeof text === 'string' && text && !text.startsWith('[superseded')) this.onReply(text);
      } catch {
        /* ignore */
      }
    }
  }

  send(transcript: string): boolean {
    if (!this.sock || this.sock.destroyed) return false;
    this.sock.write(
      JSON.stringify({
        text: PREAMBLE + transcript,
        to: { channelType: 'discord', platformId: this.cfg.dmPlatformId, threadId: null, ...(this.cfg.instance ? { instance: this.cfg.instance } : {}) },
        reply_to: { channelType: 'cli', platformId: 'local', threadId: null },
        sender: 'George',
        senderId: `discord:${this.cfg.userId}`,
      }) + '\n',
    );
    return true;
  }

  close(): void {
    this.closed = true;
    this.sock?.destroy();
  }
}
