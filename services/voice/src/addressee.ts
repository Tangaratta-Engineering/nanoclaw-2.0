import fs from 'node:fs';
import path from 'node:path';

import type { AgentKey } from './policy.ts';

/**
 * Who George is talking to, shared by the three voice services (separate processes, same machine). A named
 * utterance ("Jack, research Tasmania") sets it; unnamed follow-ups belong to that agent until George names another
 * or a few minutes pass without anyone talking to it. Best effort: a missing or unreadable file means "no one yet".
 */
export const STICKY_MS = 6 * 60_000;

export class AddresseeState {
  private file: string;
  constructor(file: string) {
    this.file = file;
  }

  /** The agents George was last talking to, if that was recent enough. */
  current(now: number = Date.now()): AgentKey[] {
    try {
      const j = JSON.parse(fs.readFileSync(this.file, 'utf8')) as { keys?: unknown; at?: unknown };
      if (typeof j.at !== 'number' || now - j.at > STICKY_MS || !Array.isArray(j.keys)) return [];
      return j.keys.filter((k): k is AgentKey => k === 'tiff' || k === 'jimmy' || k === 'jack');
    } catch {
      return [];
    }
  }

  remember(keys: AgentKey[], now: number = Date.now()): void {
    try {
      fs.mkdirSync(path.dirname(this.file), { recursive: true });
      const tmp = `${this.file}.${process.pid}.tmp`;
      fs.writeFileSync(tmp, JSON.stringify({ keys, at: now }));
      fs.renameSync(tmp, this.file);
    } catch {
      /* never block a call over this */
    }
  }
}

/**
 * Is this utterance for `mine`? Named: for whoever is named. Unnamed: for whoever George was last talking to, else
 * for the default agent (Tiff).
 */
export function isForAgent(mine: AgentKey, named: AgentKey[], state: AddresseeState, now: number = Date.now()): boolean {
  if (named.length) {
    state.remember(named, now);
    return named.includes(mine);
  }
  const current = state.current(now);
  if (current.length) {
    if (current.includes(mine)) state.remember(current, now); // the conversation continues: keep it alive
    return current.includes(mine);
  }
  return mine === 'tiff';
}
