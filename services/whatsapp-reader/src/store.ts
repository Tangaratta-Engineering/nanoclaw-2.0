import fs from 'node:fs';
import path from 'node:path';
import { DatabaseSync } from 'node:sqlite';

export interface Msg {
  id: string;
  chatJid: string;
  chatName: string;
  sender: string;
  ts: number; // unix seconds
  text: string;
  kind: string;
}

/** Messages from allow-listed chats only. The store never learns about any other chat's messages. */
export class Store {
  db: DatabaseSync;

  constructor(file: string) {
    if (file !== ':memory:') fs.mkdirSync(path.dirname(file), { recursive: true });
    this.db = new DatabaseSync(file);
    this.db.exec(`
      create table if not exists chats (jid text primary key, name text, allowed integer not null default 0);
      create table if not exists messages (
        id text not null, chat_jid text not null, sender text not null, ts integer not null,
        text text not null, kind text not null, reported_at text,
        primary key (chat_jid, id));
      create index if not exists messages_ts on messages (ts);
      create virtual table if not exists messages_fts using fts5(text, sender, chat, tokenize='porter unicode61');
    `);
  }

  setChat(jid: string, name: string | null, allowed: boolean): void {
    this.db
      .prepare('insert into chats(jid,name,allowed) values(?,?,?) on conflict(jid) do update set name=coalesce(excluded.name,name), allowed=excluded.allowed')
      .run(jid, name, allowed ? 1 : 0);
  }

  chat(jid: string): { name: string | null; allowed: boolean } | null {
    const r = this.db.prepare('select name, allowed from chats where jid=?').get(jid) as { name: string | null; allowed: number } | undefined;
    return r ? { name: r.name, allowed: !!r.allowed } : null;
  }

  chats(): { jid: string; name: string | null }[] {
    return this.db.prepare('select jid, name from chats where allowed=1 order by name').all() as { jid: string; name: string | null }[];
  }

  add(m: Msg): boolean {
    const r = this.db
      .prepare('insert or ignore into messages(id,chat_jid,sender,ts,text,kind) values(?,?,?,?,?,?)')
      .run(m.id, m.chatJid, m.sender, m.ts, m.text, m.kind);
    if (!r.changes) return false;
    this.db.prepare('insert into messages_fts(rowid,text,sender,chat) values(last_insert_rowid(),?,?,?)').run(m.text, m.sender, m.chatName);
    return true;
  }

  private rows(sql: string, ...args: (string | number)[]): Out[] {
    return (this.db.prepare(sql).all(...args) as unknown as Row[]).map(toOut);
  }

  /** Messages nobody has told George about yet, oldest first. */
  unreported(limit = 200): Out[] {
    return this.rows(`${SEL} where m.reported_at is null and c.allowed=1 order by m.ts limit ?`, limit);
  }

  markReported(keys: { chat: string; id: string }[]): number {
    const st = this.db.prepare('update messages set reported_at=? where chat_jid=? and id=? and reported_at is null');
    const now = new Date().toISOString();
    let n = 0;
    for (const k of keys) n += Number(st.run(now, k.chat, k.id).changes);
    return n;
  }

  recent(hours: number, chat?: string, limit = 200): Out[] {
    const since = Math.floor(Date.now() / 1000) - hours * 3600;
    return chat
      ? this.rows(`${SEL} where m.ts>=? and c.allowed=1 and (m.chat_jid=? or lower(c.name) like ?) order by m.ts limit ?`, since, chat, `%${chat.toLowerCase()}%`, limit)
      : this.rows(`${SEL} where m.ts>=? and c.allowed=1 order by m.ts limit ?`, since, limit);
  }

  search(q: string, limit = 20): Out[] {
    const fts = q.replace(/[^\p{L}\p{N}\s]/gu, ' ').trim().split(/\s+/).filter(Boolean).map((w) => `"${w}"`).join(' ');
    if (!fts) return [];
    return this.rows(
      `${SEL} join messages_fts f on f.rowid=m.rowid where messages_fts match ? and c.allowed=1 order by m.ts desc limit ?`,
      fts,
      limit,
    );
  }

  close(): void {
    this.db.close();
  }
}

interface Row { id: string; chat_jid: string; chat: string | null; sender: string; ts: number; text: string; kind: string; reported_at: string | null }
export interface Out { id: string; chat: string; chatJid: string; sender: string; at: string; text: string; kind: string; reported: boolean }
const SEL = 'select m.id, m.chat_jid, c.name as chat, m.sender, m.ts, m.text, m.kind, m.reported_at from messages m join chats c on c.jid=m.chat_jid';
const toOut = (r: Row): Out => ({
  id: r.id,
  chat: r.chat ?? r.chat_jid,
  chatJid: r.chat_jid,
  sender: r.sender,
  at: new Date(r.ts * 1000).toISOString(),
  text: r.text,
  kind: r.kind,
  reported: !!r.reported_at,
});
