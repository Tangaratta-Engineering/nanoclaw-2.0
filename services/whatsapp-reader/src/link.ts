import fs from 'node:fs';
import makeWASocket, { Browsers, DisconnectReason, fetchLatestBaileysVersion, useMultiFileAuthState } from '@whiskeysockets/baileys';
import { pino } from 'pino';
import QRCode from 'qrcode';

import { loadConfig } from './config.ts';

/** One-time device link. `WA_PHONE=61400000000 pnpm run link` shows a pairing code instead of a QR. */
const cfg = loadConfig();
fs.mkdirSync(cfg.authDir, { recursive: true });

async function run(): Promise<void> {
  const { state, saveCreds } = await useMultiFileAuthState(cfg.authDir);
  const { version } = await fetchLatestBaileysVersion();
  const sock = makeWASocket({ version, auth: state, browser: Browsers.macOS('Desktop'), logger: pino({ level: 'silent' }), markOnlineOnConnect: false, syncFullHistory: false, printQRInTerminal: false });
  sock.ev.on('creds.update', saveCreds);
  const phone = process.env.WA_PHONE;
  if (phone && !state.creds.registered) {
    setTimeout(async () => console.log('Pairing code (enter it in WhatsApp > Linked Devices > Link with phone number):', await sock.requestPairingCode(phone)), 3000);
  }
  sock.ev.on('connection.update', async ({ connection, qr, lastDisconnect }) => {
    if (qr && !phone) console.log(await QRCode.toString(qr, { type: 'terminal', small: true }));
    if (connection === 'open') {
      console.log('Linked. You can stop this now and start the service.');
      setTimeout(() => process.exit(0), 2000);
    }
    if (connection === 'close') {
      const code = (lastDisconnect?.error as { output?: { statusCode?: number } } | undefined)?.output?.statusCode;
      if (code === DisconnectReason.restartRequired) void run();
      else if (code === DisconnectReason.loggedOut) {
        console.log('Logged out');
        process.exit(1);
      }
    }
  });
}
void run();
