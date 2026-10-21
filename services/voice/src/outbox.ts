import fs from 'node:fs';
import path from 'node:path';
import { DatabaseSync } from 'node:sqlite';

/**
 * Watches an agent group's session outbound.db files for new text messages to the DM and hands
 * them to `onText`, but only while "armed" (shortly after George spoke), so unrelated
 * notifications are not read out during a call.
 */
export class OutboxWatcher {
  private dir: string;
  private platformId: string;
  private seen = new Map<string, number>();
  private armedUntil = 0;
  private timer: NodeJS.Timeout | null = null;
  onText: (text: string) => void = () => {};

  constructor(dir: string, platformId: string) {
    this.dir = dir;
    this.platformId = platformId;
  }

  start(): void {
    for (const p of this.files()) this.seen.set(p, this.maxSeq(p)); // ignore history
    this.timer = setInterval(() => this.poll(), 500);
  }

  stop(): void {
    if (this.timer) clearInterval(this.timer);
  }

  arm(ms: number): void {
    this.armedUntil = Math.max(this.armedUntil, Date.now() + ms);
  }

  private files(): string[] {
    try {
      return fs
        .readdirSync(this.dir)
        .map((d) => path.join(this.dir, d, 'outbound.db'))
        .filter((p) => fs.existsSync(p));
    } catch {
      return [];
    }
  }

  private open(p: string): DatabaseSync {
    return new DatabaseSync(p, { readOnly: true });
  }

  private maxSeq(p: string): number {
    try {
      const db = this.open(p);
      try {
        return (db.prepare('select coalesce(max(seq),0) m from messages_out').get() as { m: number }).m;
      } finally {
        db.close();
      }
    } catch {
      return 0;
    }
  }

  poll(): void {
    for (const p of this.files()) {
      const last = this.seen.get(p) ?? 0; // a session created after start is read from the beginning
      try {
        const db = this.open(p);
        try {
          const rows = db
            .prepare('select seq, content from messages_out where seq > ? and platform_id = ? order by seq')
            .all(last, this.platformId) as { seq: number; content: string }[];
          let max = last;
          for (const r of rows) {
            max = Math.max(max, r.seq);
            const text = textOf(r.content);
            if (text && Date.now() < this.armedUntil) this.onText(text);
          }
          // also advance past rows for other destinations
          this.seen.set(p, Math.max(max, this.maxSeqOn(db, last)));
        } finally {
          db.close();
        }
      } catch {
        /* db busy or mid-write: try again next tick */
      }
    }
  }

  private maxSeqOn(db: DatabaseSync, floor: number): number {
    const m = (db.prepare('select coalesce(max(seq),0) m from messages_out').get() as { m: number }).m;
    return Math.max(m, floor);
  }
}

export function textOf(content: string): string | null {
  try {
    const c = JSON.parse(content) as { text?: unknown };
    return typeof c.text === 'string' && c.text.trim() ? c.text : null;
  } catch {
    return null;
  }
}
