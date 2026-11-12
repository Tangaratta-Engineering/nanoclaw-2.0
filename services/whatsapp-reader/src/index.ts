import http from 'node:http';
import fs from 'node:fs';
import makeWASocket, { Browsers, DisconnectReason, fetchLatestBaileysVersion, useMultiFileAuthState } from '@whiskeysockets/baileys';
import { pino } from 'pino';

import { handle } from './api.ts';
import { isAllowed, loadAllowlist, loadConfig } from './config.ts';
import { extractText } from './extract.ts';
import { Store } from './store.ts';

const log = (...a: unknown[]) => console.log(new Date().toISOString(), ...a);
const cfg = loadConfig();
if (!cfg.apiKey) {
  console.error('WA_API_KEY is not set: refusing to start');
  process.exit(1);
}
fs.mkdirSync(cfg.dataDir, { recursive: true });
const store = new Store(cfg.dbPath);
let connected = false;

/**
 * READ-ONLY by construction: this file only listens. It never calls a send, read-receipt, presence or chat-modify
 * function (index.test.ts fails the build if one appears), and the socket is told not to announce itself online.
 */
async function connect(): Promise<void> {
  const { state, saveCreds } = await useMultiFileAuthState(cfg.authDir);
  const { version } = await fetchLatestBaileysVersion();
  const sock = makeWASocket({
    version,
    auth: state,
    browser: Browsers.macOS('Desktop'),
    logger: pino({ level: 'silent' }),
    markOnlineOnConnect: false, // do not show "online" and keep the phone's notifications
    syncFullHistory: false,
    printQRInTerminal: false,
  });
  sock.ev.on('creds.update', saveCreds);
  sock.ev.on('connection.update', ({ connection, lastDisconnect }) => {
    if (connection === 'open') {
      connected = true;
      log('connected (read-only)');
    }
    if (connection === 'close') {
      connected = false;
      const code = (lastDisconnect?.error as { output?: { statusCode?: number } } | undefined)?.output?.statusCode;
      if (code === DisconnectReason.loggedOut) {
        log('logged out: relink with `pnpm run link`');
        process.exit(1);
      }
      log('connection closed, retrying', code);
      setTimeout(() => void connect(), 5_000);
    }
  });

  const names = new Map<string, string>();
  const nameOf = async (jid: string): Promise<string | null> => {
    const known = store.chat(jid)?.name ?? names.get(jid);
    if (known) return known;
    if (!jid.endsWith('@g.us')) return null; // one-to-one chats are named by their push name below
    try {
      const meta = await sock.groupMetadata(jid);
      names.set(jid, meta.subject);
      return meta.subject;
    } catch {
      return null;
    }
  };

  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    log(`received ${messages.length} message(s) (${type})`); // counts only, never content
    if (type !== 'notify' && type !== 'append') return;
    for (const msg of messages) {
      try {
        const jid = msg.key.remoteJid;
        if (!jid || jid === 'status@broadcast' || !msg.key.id) continue;
        let name = await nameOf(jid);
        if (!jid.endsWith('@g.us') && !msg.key.fromMe && msg.pushName) name = msg.pushName; // a one-to-one chat is named by the OTHER person (pushName on our own messages is George)
        // WhatsApp may address a person by an anonymous id (@lid) and carry their phone number as the alternate id
        const alt = (msg.key as { remoteJidAlt?: string }).remoteJidAlt;
        const list = loadAllowlist(cfg.allowlistPath); // re-read each time: edits apply at once
        const allowed = isAllowed(list, jid, name) || (!!alt && isAllowed(list, alt, null));
        store.setChat(jid, name, allowed);
        if (!allowed) continue; // never stored
        const body = extractText(msg.message as Record<string, any> | null);
        if (!body) continue;
        const sender = msg.key.fromMe ? 'George' : msg.pushName || (msg.key.participant ?? jid).split('@')[0];
        store.add({ id: msg.key.id, chatJid: jid, chatName: name ?? jid, sender, ts: Number(msg.messageTimestamp ?? Math.floor(Date.now() / 1000)), text: body.text, kind: body.kind });
      } catch (e) {
        log('message skipped:', String(e).slice(0, 120));
      }
    }
  });
}

const server = http.createServer((req, res) => {
  const chunks: Buffer[] = [];
  req.on('data', (c) => chunks.push(c));
  req.on('end', () => {
    let body: unknown = null;
    try {
      body = chunks.length ? JSON.parse(Buffer.concat(chunks).toString()) : null;
    } catch {
      /* ignore */
    }
    const out = handle(store, req.method ?? 'GET', new URL(req.url ?? '/', 'http://x'), body, req.headers['x-api-key'] as string | undefined, cfg.apiKey, () => connected, () => loadAllowlist(cfg.allowlistPath));
    res.writeHead(out.status, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(out.body));
  });
});
server.listen(cfg.port, cfg.host, () => log(`api on ${cfg.host}:${cfg.port}`));
void connect();
