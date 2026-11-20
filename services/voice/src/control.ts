import fs from 'node:fs';
import net from 'node:net';
import path from 'node:path';

import type { AgentKey } from './policy.ts';

/**
 * How the one listening voice service hands work to the others (they only speak). One JSON message per connection
 * over a unix socket, answered with "ok". The socket lives in the runtime directory, which is NOT mounted into agent
 * containers, so an agent cannot talk to it.
 */
export type ControlMessage =
  | { op: 'say'; text: string; clipEnd: number } // George said this to you: send it to your agent
  | { op: 'stop' }; // stop speaking now

export const controlPath = (dir: string, key: AgentKey): string => path.join(dir, `${key}.sock`);

export function serveControl(file: string, handler: (m: ControlMessage) => void | Promise<void>, log: (...a: unknown[]) => void = () => {}): net.Server {
  fs.mkdirSync(path.dirname(file), { recursive: true, mode: 0o700 });
  fs.rmSync(file, { force: true }); // a socket left by a crashed run
  const server = net.createServer((s) => {
    let buf = '';
    s.setEncoding('utf8');
    s.on('error', () => {});
    s.on('data', async (d: string) => {
      buf += d;
      if (!buf.includes('\n')) return;
      const line = buf.slice(0, buf.indexOf('\n'));
      buf = '';
      try {
        const m = JSON.parse(line) as ControlMessage;
        if (m && (m.op === 'stop' || (m.op === 'say' && typeof m.text === 'string'))) await handler(m);
        s.end('ok\n');
      } catch (e) {
        log('control message failed:', String(e).slice(0, 120));
        s.end('error\n');
      }
    });
  });
  server.listen(file, () => fs.chmodSync(file, 0o600));
  return server;
}

/** True when the other service accepted the message. */
export function sendControl(file: string, msg: ControlMessage, timeoutMs = 2000): Promise<boolean> {
  return new Promise((resolve) => {
    const s = net.createConnection(file);
    let out = '';
    const done = (ok: boolean) => {
      s.destroy();
      resolve(ok);
    };
    s.setTimeout(timeoutMs, () => done(false));
    s.on('error', () => done(false));
    s.on('connect', () => s.write(JSON.stringify(msg) + '\n'));
    s.on('data', (d) => {
      out += d.toString();
      if (out.includes('\n')) done(out.trim() === 'ok');
    });
    s.on('end', () => done(out.trim() === 'ok'));
  });
}
