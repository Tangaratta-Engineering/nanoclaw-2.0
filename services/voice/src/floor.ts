import fs from 'node:fs';
import path from 'node:path';

/**
 * Who has the floor in the voice channel, shared by the three voice services (separate processes, same machine) so
 * two agents never talk at once. The holder refreshes the lock while it speaks; a lock nobody refreshed for
 * `STALE_MS` (a crashed service) is taken over. Best effort: if the file cannot be used the agent just speaks.
 */
export const STALE_MS = 20_000;
const POLL_MS = 150;

export class Floor {
  private file: string;
  constructor(file: string) {
    this.file = file;
  }

  private read(): { holder?: string; at?: number } | null {
    try {
      return JSON.parse(fs.readFileSync(this.file, 'utf8'));
    } catch {
      return null;
    }
  }

  /** Who is speaking now, if anyone (and it is fresh). */
  holder(now: number = Date.now()): string | null {
    const j = this.read();
    return j && typeof j.holder === 'string' && typeof j.at === 'number' && now - j.at < STALE_MS ? j.holder : null;
  }

  /** Try to take the floor. True when `me` holds it afterwards. */
  tryAcquire(me: string, now: number = Date.now()): boolean {
    try {
      fs.mkdirSync(path.dirname(this.file), { recursive: true });
      const current = this.holder(now);
      if (current && current !== me) return false;
      if (current === me) return this.refresh(me, now);
      try {
        fs.rmSync(this.file, { force: true });
        fs.writeFileSync(this.file, JSON.stringify({ holder: me, at: now }), { flag: 'wx' });
      } catch {
        return false; // someone else created it in the same instant
      }
      return true;
    } catch {
      return true; // never block a call over this
    }
  }

  refresh(me: string, now: number = Date.now()): boolean {
    try {
      if (this.holder(now) !== me) return false;
      fs.writeFileSync(this.file, JSON.stringify({ holder: me, at: now }));
      return true;
    } catch {
      return true;
    }
  }

  release(me: string): void {
    try {
      if (this.read()?.holder === me) fs.rmSync(this.file, { force: true });
    } catch {
      /* ignore */
    }
  }

  /** Wait for the floor, up to `maxWaitMs` (then speak anyway: a late answer beats none). Returns who we waited for. */
  async acquire(me: string, maxWaitMs = 40_000, sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms))): Promise<string | null> {
    const t0 = Date.now();
    let waitedFor: string | null = null;
    while (!this.tryAcquire(me)) {
      waitedFor = this.holder();
      if (Date.now() - t0 > maxWaitMs) return waitedFor;
      await sleep(POLL_MS);
    }
    return waitedFor;
  }
}
