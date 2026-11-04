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

/**
 * Google Chirp 3 HD worker: one long-running `python3 google_server.py` started under `onecli run`, so the vault
 * injects the API key. Same line protocol as the Piper worker. Sentences are synthesised in parallel by the worker.
 */
export class GoogleTtsWorker {
  private cfg: Config;
  private proc: ChildProcessWithoutNullStreams | null = null;
  private dir = '';
  private nextId = 1;
  private pending = new Map<number, Pending>();
  private ready: Promise<void> | null = null;

  constructor(cfg: Config) {
    this.cfg = cfg;
  }

  private start(): Promise<void> {
    const c = this.cfg;
    this.dir = fs.mkdtempSync(path.join(os.tmpdir(), 'voice-gtts-'));
    const proc = spawn(
      'onecli',
      ['run', '--agent', c.onecliAgent, '--', 'python3', path.join(c.skillsDir, 'speak/scripts/google_server.py'), '--voice', c.googleVoice!],
      { stdio: ['pipe', 'pipe', 'pipe'], env: { ...process.env, SPEAK_GOOGLE_USAGE: c.googleUsageFile } },
    );
    this.proc = proc;
    let onReady!: () => void;
    let onFail!: (e: Error) => void;
    const ready = new Promise<void>((res, rej) => ((onReady = res), (onFail = rej)));
    readline.createInterface({ input: proc.stdout }).on('line', (line) => {
      let m: { ready?: boolean; id?: number; path?: string; error?: string };
      try {
        m = JSON.parse(line);
      } catch {
        return; // "onecli: gateway connected ..." banner lines
      }
      if (m.ready) return onReady();
      const p = m.id !== undefined ? this.pending.get(m.id) : undefined;
      if (!p) return;
      this.pending.delete(m.id!);
      if (m.error || !m.path) p.reject(new Error(m.error ?? 'no output'));
      else p.resolve(m.path);
    });
    proc.stderr.on('data', () => {});
    proc.on('exit', () => {
      onFail(new Error('google worker exited before it was ready'));
      if (this.proc !== proc) return;
      this.proc = null;
      this.ready = null;
      for (const p of this.pending.values()) p.reject(new Error('google worker exited'));
      this.pending.clear();
    });
    return ready;
  }

  warm(): void {
    if (!this.proc) this.ready = this.start();
    this.ready?.catch(() => {}); // surfaced on the first synthesize()
  }

  async synthesize(text: string): Promise<string> {
    this.warm();
    await this.ready;
    const id = this.nextId++;
    const out = path.join(this.dir, `g${id}.ogg`);
    return new Promise<string>((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.proc!.stdin.write(JSON.stringify({ id, text, out }) + '\n');
      setTimeout(() => {
        if (this.pending.delete(id)) reject(new Error('google tts timeout'));
      }, 20_000);
    });
  }

  stop(): void {
    const proc = this.proc;
    this.proc = null;
    this.ready = null;
    for (const p of this.pending.values()) p.reject(new Error('google worker stopped'));
    this.pending.clear();
    proc?.kill();
    if (this.dir) fs.rmSync(this.dir, { recursive: true, force: true });
    this.dir = '';
  }
}

interface Synth {
  warm(): void;
  synthesize(text: string): Promise<string>;
  stop(): void;
}

/**
 * What the voice service talks to. With a Google voice configured it tries Google first and falls back to the local
 * Piper worker on any failure. After two failures in a row it stays on Piper for a minute before trying Google again,
 * so an outage costs one slow sentence, not a delay on every one. Without a Google voice it is just Piper.
 */
export class Speaker {
  private failures = 0;
  private pausedUntil = 0;
  private piper: Synth;
  private google: Synth | null;
  private now: () => number;
  private log: (...a: unknown[]) => void;

  constructor(piper: Synth, google: Synth | null, now: () => number = Date.now, log: (...a: unknown[]) => void = () => {}) {
    this.piper = piper;
    this.google = google;
    this.now = now;
    this.log = log;
  }

  /** Start the voice for the call: Google when configured (Piper stays cold until needed), else Piper. */
  warm(): void {
    if (this.google) this.google.warm();
    else this.piper.warm();
  }

  async synthesize(text: string): Promise<string> {
    if (this.google && this.now() >= this.pausedUntil) {
      try {
        const file = await this.google.synthesize(text);
        this.failures = 0;
        return file;
      } catch (e) {
        this.failures++;
        this.log('google tts failed, using the local voice:', String(e).slice(0, 160));
        if (this.failures >= 2) this.pausedUntil = this.now() + 60_000;
      }
    }
    return this.piper.synthesize(text);
  }

  stop(): void {
    this.google?.stop();
    this.piper.stop();
  }
}
