import fs from 'node:fs';
import path from 'node:path';

/**
 * What the agents have just said out loud, shared by the three voice services (separate processes, same machine).
 *
 * With the call on speaker, George's microphone picks up Jack or Jimmy speaking and Discord sends it back as if he
 * had said it, so every agent "hears" George saying the other agent's reply. Each service records its own speech
 * here; a transcript that is mostly the words of something said in the last few seconds is that echo, not George.
 * Best effort: if the file cannot be used nothing is filtered.
 */
export const KEEP_MS = 5 * 60_000;
export const TAIL_MS = 15_000; // the echo is transcribed after the clip ends, plus recognition time
const LEAD_MS = 3_000;
const WORDS_PER_SEC = 2.6;
const MIN_WORDS = 3;
const WORD_RATIO = 0.7;
const PAIR_RATIO = 0.4;

interface Entry {
  id: string;
  agent: string;
  text: string;
  start: number;
  end: number;
}

const words = (t: string): string[] =>
  t
    .toLowerCase()
    .replace(/[^a-z0-9' ]+/g, ' ')
    .split(/\s+/)
    .filter(Boolean);

const pairs = (w: string[]): string[] => w.slice(1).map((x, i) => `${w[i]} ${x}`);

export class SpokenLog {
  private file: string;
  constructor(file: string) {
    this.file = file;
  }

  private read(): Entry[] {
    try {
      const j = JSON.parse(fs.readFileSync(this.file, 'utf8'));
      return Array.isArray(j) ? j : [];
    } catch {
      return [];
    }
  }

  private write(entries: Entry[]): void {
    try {
      fs.mkdirSync(path.dirname(this.file), { recursive: true });
      const tmp = `${this.file}.${process.pid}.tmp`;
      fs.writeFileSync(tmp, JSON.stringify(entries));
      fs.renameSync(tmp, this.file);
    } catch {
      /* best effort */
    }
  }

  /** Note that `agent` starts saying `text` now; the end is estimated until `finish` gives the real one. */
  record(agent: string, text: string, now: number = Date.now()): string {
    const id = `${agent}-${now}-${Math.floor(Math.random() * 1e6)}`;
    const est = (words(text).length / WORDS_PER_SEC) * 1000 + 2_000;
    this.write([...this.read().filter((e) => now - e.end < KEEP_MS), { id, agent, text, start: now, end: now + est }]);
    return id;
  }

  finish(id: string, now: number = Date.now()): void {
    const all = this.read();
    const e = all.find((x) => x.id === id);
    if (!e) return;
    e.end = now;
    this.write(all);
  }

  /** The agent whose recent speech `heard` repeats, or null when it looks like George. */
  echoOf(heard: string, now: number = Date.now()): string | null {
    const h = words(heard);
    if (h.length < MIN_WORDS) return null;
    const live = this.read().filter((e) => now >= e.start - LEAD_MS && now <= e.end + TAIL_MS);
    if (!live.length) return null;
    const known = new Set(live.flatMap((e) => words(e.text)));
    const knownPairs = new Set(live.flatMap((e) => pairs(words(e.text))));
    const wordRatio = h.filter((w) => known.has(w)).length / h.length;
    const hp = pairs(h);
    const pairRatio = hp.filter((p) => knownPairs.has(p)).length / hp.length;
    if (wordRatio < WORD_RATIO || pairRatio < PAIR_RATIO) return null;
    return live[live.length - 1].agent;
  }
}
