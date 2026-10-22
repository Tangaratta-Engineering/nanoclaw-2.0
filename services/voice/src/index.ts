/**
 * Live voice call for one NanoClaw agent.
 *
 *   George speaks → silence detected → Groq transcript → agent (DM session, via the CLI socket)
 *   → agent's short reply → Piper speech → played into the voice channel.
 */
import fs from 'node:fs';

import {
  EndBehaviorType,
  StreamType,
  VoiceConnectionStatus,
  type VoiceConnection,
  AudioPlayerStatus,
  createAudioPlayer,
  createAudioResource,
  entersState,
  joinVoiceChannel,
} from '@discordjs/voice';
import { Client, GatewayIntentBits, type Guild } from 'discord.js';
import prism from 'prism-media';

import { sendToAgent } from './agent.ts';
import { durationSecs, rms, toMono16k } from './audio.ts';
import { loadConfig } from './config.ts';
import { OutboxWatcher } from './outbox.ts';
import { isForMe, isLeadIn, isNoise, isSleepCommand, isStopCommand, lifecycleAction, startsWithName, voiceSummary, wantsFullReadout } from './policy.ts';
import { transcribe } from './stt.ts';
import { synthesize } from './tts.ts';

const MIN_SECS = 0.5;
const MIN_RMS = 0.005;
const SILENCE_MS = 1500; // let a thought finish before cutting the clip
const MAX_SPOKEN_PER_TURN = 1; // agent messages spoken per turn; the rest stay as text
const TURN_GAP_MS = 15_000; // a message this long after the last spoken one starts a new turn (e.g. a task result)
const DEBOUNCE_MS = 2200; // wait for a continuation before sending, so a dictation is one message not three

const cfg = loadConfig();
const log = (...a: unknown[]) => console.log(new Date().toISOString(), ...a);

const client = new Client({ intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildVoiceStates] });
const player = createAudioPlayer();
const outbox = new OutboxWatcher(cfg.sessionsDir, cfg.dmPlatformId);
const speechQueue: string[] = [];
let speaking = false;
let generation = 0; // bumped on stop so in-flight synthesis is discarded
let spokenThisTurn = 0;
let lastSpokenAt = 0;
let fullReadout = false;
const utterBuf: string[] = [];
let debounce: NodeJS.Timeout | null = null;
const pending: string[] = []; // things George said while she was talking, sent when she finishes

const busy = () => speaking || speechQueue.length > 0;

function stopSpeaking(): void {
  generation++;
  speechQueue.length = 0;
  pending.length = 0;
  if (player.state.status === AudioPlayerStatus.Playing) player.stop(true);
}

async function drainSpeech(): Promise<void> {
  if (speaking) return;
  speaking = true;
  try {
    while (speechQueue.length) {
      const text = speechQueue.shift()!;
      const gen = generation;
      let file: string;
      try {
        file = await synthesize(cfg, text);
      } catch (err) {
        log('tts failed', String(err).slice(0, 200));
        continue;
      }
      if (gen !== generation) {
        fs.rmSync(file, { force: true });
        continue;
      }
      player.play(createAudioResource(fs.createReadStream(file), { inputType: StreamType.OggOpus }));
      await entersState(player, AudioPlayerStatus.Playing, 5_000).catch(() => {});
      await entersState(player, AudioPlayerStatus.Idle, 120_000).catch(() => {});
      fs.rmSync(file, { force: true });
    }
  } finally {
    speaking = false;
  }
  if (pending.length) {
    const said = pending.splice(0).join(' ');
    log('sending what you said while she was talking:', said);
    outbox.arm(120_000);
    fullReadout = wantsFullReadout(said);
    spokenThisTurn = 0;
    void sendToAgent(cfg, said);
  }
}

outbox.onText = (text) => {
  log('agent →', text.slice(0, 120));
  outbox.arm(45_000); // keep listening for follow-up messages from the same task
  if (/^details\b/i.test(text.trim()) || isLeadIn(text)) return; // text-only follow-ups
  if (Date.now() - lastSpokenAt > TURN_GAP_MS) spokenThisTurn = 0;
  if (spokenThisTurn >= (fullReadout ? 4 : MAX_SPOKEN_PER_TURN)) return; // long replies live in the text chat
  spokenThisTurn++;
  lastSpokenAt = Date.now();
  speechQueue.push(fullReadout ? voiceSummary(text, 900) : voiceSummary(text));
  void drainSpeech();
};

async function handleUtterance(pcm: Buffer): Promise<void> {
  const samples = toMono16k(pcm);
  if (durationSecs(samples) < MIN_SECS || rms(samples) < MIN_RMS) return;
  const t0 = Date.now();
  const { text, reliability } = await transcribe(cfg, samples);
  log(`heard (${reliability}, ${Date.now() - t0}ms):`, text);
  const wasBusy = busy();
  if (isSleepCommand(text)) {
    log('sleep command: no longer listening until George unmutes or rejoins');
    asleep = true;
    stopSpeaking();
    utterBuf.length = 0;
    if (!cfg.wakeNames.length || startsWithName(text, cfg.wakeNames)) {
      speechQueue.push("Okay, I've stopped listening. Unmute yourself or rejoin the channel to wake me.");
      void drainSpeech();
    }
    return;
  }
  if (asleep) return; // a clip captured just before "go to sleep" must not be acted on
  if (isStopCommand(text)) {
    log('stop command');
    stopSpeaking();
    return;
  }
  if (!isForMe(text, cfg.wakeNames, cfg.otherNames)) {
    log('not for me:', text.slice(0, 60));
    return;
  }
  if (isNoise(text, reliability, wasBusy)) return;
  if (reliability === 'poor') {
    speechQueue.push("Sorry, I didn't catch that. Could you say it again?");
    void drainSpeech();
    return;
  }
  utterBuf.push(text);
  if (debounce) clearTimeout(debounce);
  debounce = setTimeout(() => void flushUtterances(), DEBOUNCE_MS);
}

/** Send everything George said in one go once he has paused long enough. */
async function flushUtterances(): Promise<void> {
  debounce = null;
  const said = utterBuf.splice(0).join(' ').trim();
  if (!said) return;
  if (busy()) {
    pending.push(said); // low tolerance for interruption: she finishes her thought first
    return;
  }
  fullReadout = wantsFullReadout(said);
  spokenThisTurn = 0;
  outbox.arm(120_000);
  log('→ agent:', said.slice(0, 160));
  if (!(await sendToAgent(cfg, said))) {
    speechQueue.push("I can't reach my brain right now. Try again in a moment.");
    void drainSpeech();
  }
}

const LEAVE_GRACE_MS = 3 * 60_000; // stay a little after George leaves, in case he drops out and rejoins
const CHECK_MS = 30_000;

let connection: VoiceConnection | null = null;
let joining = false;
let asleep = false; // "go to sleep": nothing is captured or sent anywhere until George unmutes or rejoins
let leaveTimer: NodeJS.Timeout | null = null;
let guild: Guild;

const georgeState = () => guild.voiceStates.cache.get(cfg.userId);
const georgeInChannel = () => georgeState()?.channelId === cfg.channelId;
const alive = () => !!connection && connection.state.status !== VoiceConnectionStatus.Destroyed;

function listen(conn: VoiceConnection): void {
  const active = new Set<string>();
  conn.receiver.speaking.on('start', (userId) => {
    if (userId !== cfg.userId || asleep || active.has(userId)) return;
    active.add(userId);
    const opus = conn.receiver.subscribe(userId, { end: { behavior: EndBehaviorType.AfterSilence, duration: SILENCE_MS } });
    const decoder = new prism.opus.Decoder({ rate: 48000, channels: 2, frameSize: 960 });
    const chunks: Buffer[] = [];
    opus.pipe(decoder);
    decoder.on('data', (c: Buffer) => chunks.push(c));
    decoder.on('end', () => {
      active.delete(userId);
      handleUtterance(Buffer.concat(chunks)).catch((e) => log('utterance error', String(e).slice(0, 200)));
    });
    opus.on('error', () => active.delete(userId));
  });
}

async function join(): Promise<void> {
  if (joining || alive()) return;
  joining = true;
  try {
    const conn = joinVoiceChannel({
      channelId: cfg.channelId,
      guildId: cfg.guildId,
      adapterCreator: guild.voiceAdapterCreator,
      selfDeaf: false,
      debug: !!process.env.VOICE_DEBUG,
    });
    conn.on('stateChange', (o, n) => log('voice state:', o.status, '→', n.status));
    if (process.env.VOICE_DEBUG) conn.on('debug', (m) => log('voice debug:', m));
    // Discord moved us or dropped the link: give it a few seconds to renegotiate, otherwise start over.
    conn.on(VoiceConnectionStatus.Disconnected, async () => {
      try {
        await Promise.race([entersState(conn, VoiceConnectionStatus.Signalling, 5_000), entersState(conn, VoiceConnectionStatus.Connecting, 5_000)]);
      } catch {
        if (conn.state.status !== VoiceConnectionStatus.Destroyed) conn.destroy();
      }
    });
    conn.on(VoiceConnectionStatus.Destroyed, () => {
      if (connection === conn) connection = null;
    });
    connection = conn;
    await entersState(conn, VoiceConnectionStatus.Ready, 30_000);
    conn.subscribe(player);
    listen(conn);
    log(`joined: ${cfg.agentName} is in the voice channel`);
  } catch (e) {
    log('join failed, will retry:', String(e).slice(0, 150));
    connection?.destroy();
    connection = null;
  } finally {
    joining = false;
  }
}

function leave(): void {
  leaveTimer = null;
  stopSpeaking();
  connection?.destroy();
  connection = null;
  log('left: George is not in the channel');
}

/** Join when George is in the channel, leave (after a grace period) when he is not, rejoin if the link died. */
function reconcile(): void {
  const act = lifecycleAction({ georgeInChannel: georgeInChannel(), connected: alive(), leaving: !!leaveTimer });
  if (act === 'join') void join();
  else if (act === 'schedule-leave') leaveTimer = setTimeout(leave, LEAVE_GRACE_MS);
  else if (act === 'cancel-leave' && leaveTimer) {
    clearTimeout(leaveTimer);
    leaveTimer = null;
  }
}

async function main(): Promise<void> {
  const ready = new Promise<void>((r) => client.once('clientReady', () => r()));
  await client.login(cfg.token);
  await ready;
  if (process.env.VOICE_DEBUG) client.on('raw', (p: { t?: string }) => p.t?.startsWith('VOICE') && log('raw', p.t));
  guild = client.guilds.cache.get(cfg.guildId) ?? (await client.guilds.fetch(cfg.guildId));
  log('gateway ready');
  outbox.start();

  client.on('voiceStateUpdate', (before, after) => {
    if (after.id !== cfg.userId) return;
    const arrived = before.channelId !== cfg.channelId && after.channelId === cfg.channelId;
    const unmuted = !!before.selfMute && !after.selfMute;
    if (arrived || unmuted) {
      if (asleep) log('waking up');
      asleep = false; // rejoining or unmuting yourself is the wake-up signal
    }
    reconcile();
  });
  reconcile();
  setInterval(reconcile, CHECK_MS);
}

main().catch((err) => {
  console.error('voice service failed:', err);
  process.exit(1);
});

for (const sig of ['SIGINT', 'SIGTERM'] as const) {
  process.on(sig, () => {
    outbox.stop();
    client.destroy();
    process.exit(0);
  });
}
