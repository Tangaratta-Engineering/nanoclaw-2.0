import fs from 'node:fs';
import makeWASocket, { Browsers, DisconnectReason, fetchLatestBaileysVersion, useMultiFileAuthState } from '@whiskeysockets/baileys';
import { pino } from 'pino';
import QRCode from 'qrcode';

import { loadConfig } from './config.ts';

/**
 * One-time device link. `WA_PHONE=61400000000 pnpm run link` shows a pairing code instead of a QR.
 * A half-finished earlier attempt is wiped first (it makes WhatsApp answer "logged out").
 */
const cfg = loadConfig();
const phone = process.env.WA_PHONE?.replace(/\D/g, '');
const say = (...a: unknown[]) => console.log(new Date().toISOString().slice(11, 19), ...a);

function freshAuthDir(): void {
  try {
    const creds = JSON.parse(fs.readFileSync(`${cfg.authDir}/creds.json`, 'utf8'));
    if (creds.registered) {
      say('Already linked. Nothing to do (delete the auth folder to link again).');
      process.exit(0);
    }
  } catch {
    /* none yet */
  }
  fs.rmSync(cfg.authDir, { recursive: true, force: true });
  fs.mkdirSync(cfg.authDir, { recursive: true });
}

let attempts = 0;
async function run(): Promise<void> {
  const { state, saveCreds } = await useMultiFileAuthState(cfg.authDir);
  const { version } = await fetchLatestBaileysVersion();
  const sock = makeWASocket({ version, auth: state, browser: phone ? Browsers.ubuntu('Chrome') : Browsers.macOS('Desktop'), logger: pino({ level: 'silent' }), markOnlineOnConnect: false, syncFullHistory: false, printQRInTerminal: false });
  sock.ev.on('creds.update', saveCreds);
  let asked = false;
  sock.ev.on('connection.update', async ({ connection, qr, lastDisconnect }) => {
    if (qr && !asked) {
      asked = true;
      if (phone && !state.creds.registered) {
        const code = await sock.requestPairingCode(phone);
        say(`Pairing code: ${code}`);
        say('On the phone: WhatsApp > Settings > Linked Devices > Link a Device > "Link with phone number instead". Enter it within a minute. Leave this running.');
      } else {
        say('Scan this in WhatsApp > Settings > Linked Devices > Link a Device:');
        console.log(await QRCode.toString(qr, { type: 'terminal', small: true }));
      }
    }
    if (connection === 'open') {
      say('Linked. You can stop this now and start the service.');
      setTimeout(() => process.exit(0), 2000);
    }
    if (connection === 'close') {
      const code = (lastDisconnect?.error as { output?: { statusCode?: number } } | undefined)?.output?.statusCode;
      say('connection closed, code', code);
      if (code === DisconnectReason.restartRequired) return void run(); // normal right after pairing
      if (code === DisconnectReason.loggedOut) {
        say('WhatsApp refused the link (logged out). Wait a minute and run it again.');
        fs.rmSync(cfg.authDir, { recursive: true, force: true });
        process.exit(1);
      }
      if (++attempts > 3) {
        say('Giving up after several tries.');
        process.exit(1);
      }
      void run();
    }
  });
}

freshAuthDir();
setTimeout(() => {
  say('Timed out waiting for the link. Run it again for a new code.');
  process.exit(1);
}, 4 * 60_000);
void run();
