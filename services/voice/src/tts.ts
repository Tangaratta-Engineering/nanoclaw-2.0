import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import readline from 'node:readline';

import type { Config } from './config.ts';

interface Pending {
  resolve: (p: string) => void;
  reject: (e: Error) => void;
}

/**
 * Keeps one Piper worker container running (voice loaded once), so speech takes well under a second
 * per sentence instead of starting a container and reloading the model every time.
 */
export class TtsWorker {
  private cfg: Config;
  private proc: ChildProcessWithoutNullStreams | null = null;
  private dir = '';
  private name = '';
  private nextId = 1;
  private pending = new Map<number, Pending>();
  private ready: Promise<void> | null = null;

  constructor(cfg: Config) {
    this.cfg = cfg;
  }

  private start(): Promise<void> {
    const c = this.cfg;
    this.dir = fs.mkdtempSync(path.join(os.tmpdir(), 'voice-tts-'));
    fs.chmodSync(this.dir, 0o777); // the container user differs from the host user
    // Named + --init so stop() can kill the container itself: python3 as PID 1 ignores SIGTERM, so killing
    // only the docker client left the worker (and its deleted /out dir) running, and the next call reused it.
    this.name = `voice-tts-${process.pid}-${Date.now()}`;
    const proc = spawn(
      'docker',
      [
        'run',
        '--rm',
        '-i',
        '--init',
        '--name',
        this.name,
        '--network',
        'none',
        '-v',
        `${c.skillsDir}:/app/skills:ro`,
        '-v',
        `${c.piperHome}:/piper:ro`,
        '-v',
        `${this.dir}:/out`,
        '-e',
        'PIPER_HOME=/piper',
        '-e',
        'SPEAK_MAX_CHARS=2600', // the worker's own cap; the service already limits what it sends
        '--entrypoint',
        'python3',
        c.agentImage,
        '/app/skills/speak/scripts/speak_server.py',
        '--voice',
        c.voiceId,
      ],
      { stdio: ['pipe', 'pipe', 'pipe'] },
    );
    this.proc = proc;
    let onReady!: () => void;
    const ready = new Promise<void>((r) => (onReady = r));
    readline.createInterface({ input: proc.stdout }).on('line', (line) => {
      let m: { ready?: boolean; id?: number; path?: string; error?: string };
      try {
        m = JSON.parse(line);
      } catch {
        return;
      }
      if (m.ready) return onReady();
      const p = m.id !== undefined ? this.pending.get(m.id) : undefined;
      if (!p) return;
      this.pending.delete(m.id!);
      if (m.error || !m.path) p.reject(new Error(m.error ?? 'no output'));
      else p.resolve(path.join(this.dir, path.basename(m.path)));
    });
    proc.stderr.on('data', () => {});
    proc.on('exit', () => {
      if (this.proc !== proc) return; // a replaced worker; state already belongs to the new one
      this.proc = null;
      this.ready = null;
      for (const p of this.pending.values()) p.reject(new Error('tts worker exited'));
      this.pending.clear();
    });
    return ready;
  }

  /** Start the worker ahead of the first sentence so the model is already loaded. */
  warm(): void {
    if (!this.proc) this.ready = this.start();
  }

  async synthesize(text: string): Promise<string> {
    try {
      return await this.synthesizeOnce(text);
    } catch (e) {
      // e.g. the worker's /out dir was removed under it: start a fresh worker and retry once
      if (!/FileNotFoundError|worker (exited|stopped)/.test(String((e as Error).message))) throw e;
      this.stop();
      return this.synthesizeOnce(text);
    }
  }

  private async synthesizeOnce(text: string): Promise<string> {
    this.warm();
    await this.ready;
    const id = this.nextId++;
    return new Promise<string>((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.proc!.stdin.write(JSON.stringify({ id, text, out: `/out/r${id}.ogg` }) + '\n');
      setTimeout(() => {
        if (this.pending.delete(id)) reject(new Error('tts timeout'));
      }, 60_000);
    });
  }

  /** Stop the worker (e.g. when leaving the channel); the next `warm()` starts a fresh one. */
  stop(): void {
    const proc = this.proc;
    // Forget the worker immediately so the next warm() starts a fresh one with a fresh output dir.
    this.proc = null;
    this.ready = null;
    for (const p of this.pending.values()) p.reject(new Error('tts worker stopped'));
    this.pending.clear();
    proc?.kill();
    if (this.name) spawn('docker', ['rm', '-f', this.name], { stdio: 'ignore' }).on('error', () => {});
    if (this.dir) fs.rmSync(this.dir, { recursive: true, force: true });
    this.dir = '';
    this.name = '';
  }
}
