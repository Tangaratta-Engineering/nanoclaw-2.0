/**
 * ncl — chat with your NanoClaw agent from the terminal.
 *
 * Usage:
 *   pnpm run chat <message...>
 *   pnpm run chat --to <channelType>:<platformId> [--instance <name>] <message...>
 *
 * `--to` injects the message into a specific wired messaging group (see
 * `ncl messaging-groups list`), e.g. `--to discord:discord:@me:149...`.
 * `--instance` names the adapter instance that owns the chat (the `instance` column), e.g. `timmy`.
 *
 * Sends the message through the CLI channel (Unix socket) to the wired agent.
 * Reads replies until the stream goes quiet, then exits.
 *
 * Preconditions: NanoClaw host service running, an agent group wired to
 * `cli/local` via `/init-first-agent` or `/manage-channels`.
 */
import net from 'net';
import path from 'path';

import { DATA_DIR } from '../src/config.js';

const SILENCE_MS = 2000; // exit after this much quiet time following the first reply
const TOTAL_TIMEOUT_MS = 120_000; // hard stop

function socketPath(): string {
  return path.join(DATA_DIR, 'cli.sock');
}

function main(): void {
  const words = process.argv.slice(2);
  let to: { channelType: string; platformId: string; threadId: null; instance?: string } | undefined;
  if (words[0] === '--to') {
    const target = words[1] ?? '';
    const sep = target.indexOf(':');
    if (sep < 1) {
      console.error('usage: pnpm run chat --to <channelType>:<platformId> <message...>');
      process.exit(1);
    }
    to = { channelType: target.slice(0, sep), platformId: target.slice(sep + 1), threadId: null };
    words.splice(0, 2);
    if (words[0] === '--instance') {
      to.instance = words[1];
      words.splice(0, 2);
    }
  }
  if (words.length === 0) {
    console.error('usage: pnpm run chat [--to <channelType>:<platformId>] <message...>');
    process.exit(1);
  }
  const text = words.join(' ');

  const socket = net.connect(socketPath());

  socket.on('error', (err) => {
    const e = err as NodeJS.ErrnoException;
    if (e.code === 'ENOENT' || e.code === 'ECONNREFUSED') {
      console.error(`NanoClaw daemon not reachable at ${socketPath()}.`);
      console.error('Start the service (launchctl/systemd) before running ncl.');
    } else {
      console.error('CLI socket error:', err);
    }
    process.exit(2);
  });

  let firstReplySeen = false;
  let silenceTimer: NodeJS.Timeout | null = null;
  let hardTimer: NodeJS.Timeout | null = null;

  function scheduleExit(): void {
    if (silenceTimer) clearTimeout(silenceTimer);
    silenceTimer = setTimeout(() => {
      socket.end();
      process.exit(0);
    }, SILENCE_MS);
  }

  socket.on('connect', () => {
    socket.write(JSON.stringify(to ? { text, to } : { text }) + '\n');
    hardTimer = setTimeout(() => {
      if (!firstReplySeen) {
        console.error(`timeout: no reply in ${TOTAL_TIMEOUT_MS}ms`);
        socket.end();
        process.exit(3);
      }
    }, TOTAL_TIMEOUT_MS);
  });

  let buffer = '';
  socket.on('data', (chunk) => {
    buffer += chunk.toString('utf8');
    let idx: number;
    while ((idx = buffer.indexOf('\n')) >= 0) {
      const line = buffer.slice(0, idx).trim();
      buffer = buffer.slice(idx + 1);
      if (!line) continue;
      try {
        const msg = JSON.parse(line);
        if (typeof msg.text === 'string') {
          process.stdout.write(msg.text + '\n');
          firstReplySeen = true;
          if (hardTimer) {
            clearTimeout(hardTimer);
            hardTimer = null;
          }
          scheduleExit();
        }
      } catch {
        // Ignore non-JSON lines — forward compatibility.
      }
    }
  });

  socket.on('close', () => {
    if (silenceTimer) clearTimeout(silenceTimer);
    if (hardTimer) clearTimeout(hardTimer);
    process.exit(firstReplySeen ? 0 : 3);
  });
}

main();
