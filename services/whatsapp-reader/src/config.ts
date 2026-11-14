import fs from 'node:fs';
import path from 'node:path';

export interface Allowlist {
  /** A group or chat is read when its name starts with one of these (case-insensitive). */
  namePrefixes: string[];
  /** Or when its id is listed here. */
  jids: string[];
  /** Names to show for chats by id, e.g. { "61400000000@s.whatsapp.net": "James Wong" }. */
  labels?: Record<string, string>;
}

export interface Config {
  dataDir: string;
  dbPath: string;
  authDir: string;
  allowlistPath: string;
  port: number;
  host: string;
  apiKey: string;
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): Config {
  const home = env.HOME ?? '';
  const dataDir = env.WA_DATA_DIR || path.join(home, 'projects/.nanoclaw-data/whatsapp');
  return {
    dataDir,
    dbPath: path.join(dataDir, 'messages.db'),
    authDir: path.join(dataDir, 'auth'),
    allowlistPath: path.join(dataDir, 'allowlist.json'),
    port: Number(env.WA_PORT || '8772'),
    host: env.WA_HOST || '0.0.0.0',
    apiKey: env.WA_API_KEY || '',
  };
}

export function loadAllowlist(file: string): Allowlist {
  try {
    const raw = JSON.parse(fs.readFileSync(file, 'utf8')) as Partial<Allowlist>;
    return { namePrefixes: raw.namePrefixes ?? [], jids: raw.jids ?? [], labels: raw.labels ?? {} };
  } catch {
    return { namePrefixes: [], jids: [] }; // nothing allowed until George says which chats
  }
}

export function isAllowed(list: Allowlist, jid: string, name: string | null): boolean {
  if (list.jids.includes(jid)) return true;
  const n = (name ?? '').trim().toLowerCase();
  return !!n && list.namePrefixes.some((p) => p.trim() && n.startsWith(p.trim().toLowerCase()));
}

/** The name George gave a chat in the allowlist, looking under every id WhatsApp may use for that person. */
export function labelFor(list: Allowlist, ...ids: (string | null | undefined)[]): string | null {
  for (const id of ids) if (id && list.labels?.[id]) return list.labels[id];
  return null;
}
