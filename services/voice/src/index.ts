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
  AudioPlayerStatus,
  createAudioPlayer,
  createAudioResource,
  entersState,
  joinVoiceChannel,
} from '@discordjs/voice';
import { Client, GatewayIntentBits } from 'discord.js';
import prism from 'prism-media';

import { sendToAgent } from './agent.ts';
import { durationSecs, rms, toMono16k } from './audio.ts';
import { loadConfig } from './config.ts';
import { OutboxWatcher } from './outbox.ts';
import { isNoise, isStopCommand, voiceSummary } from './policy.ts';
import { transcribe } from './stt.ts';
import { synthesize } from './tts.ts';

const MIN_SECS = 0.5;
const MIN_RMS = 0.005;
const SILENCE_MS = 1500; // let a thought finish before cutting the clip
const MAX_SPOKEN_PER_TURN = 2; // agent messages spoken per utterance; the rest stay as text

const cfg = loadConfig();
const log = (...a: unknown[]) => console.log(new Date().toISOString(), ...a);

const client = new Client({ intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildVoiceStates] });
const player = createAudioPlayer();
const outbox = new OutboxWatcher(cfg.sessionsDir, cfg.dmPlatformId);
const speechQueue: string[] = [];
let speaking = false;
let generation = 0; // bumped on stop so in-flight synthesis is discarded
let spokenThisTurn = 0;
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
    spokenThisTurn = 0;
    void sendToAgent(cfg, said);
  }
}

outbox.onText = (text) => {
  log('agent →', text.slice(0, 120));
  outbox.arm(45_000); // keep listening for follow-up messages from the same task
  if (spokenThisTurn >= MAX_SPOKEN_PER_TURN) return; // long replies live in the text chat
  spokenThisTurn++;
  speechQueue.push(voiceSummary(text));
  void drainSpeech();
};

async function handleUtterance(pcm: Buffer): Promise<void> {
  const samples = toMono16k(pcm);
  if (durationSecs(samples) < MIN_SECS || rms(samples) < MIN_RMS) return;
  const t0 = Date.now();
  const { text, reliability } = await transcribe(cfg, samples);
  log(`heard (${reliability}, ${Date.now() - t0}ms):`, text);
  const wasBusy = busy();
  if (isStopCommand(text)) {
    log('stop command');
    stopSpeaking();
    return;
  }
  if (isNoise(text, reliability, wasBusy)) return;
  if (wasBusy) {
    pending.push(text); // low tolerance for interruption: finish her thought first
    return;
  }
  spokenThisTurn = 0;
  if (reliability === 'poor') {
    speechQueue.push("Sorry, I didn't catch that. Could you say it again?");
    void drainSpeech();
    return;
  }
  outbox.arm(120_000);
  if (!(await sendToAgent(cfg, text))) {
    speechQueue.push("I can't reach my brain right now. Try again in a moment.");
    void drainSpeech();
  }
}

async function main(): Promise<void> {
  const ready = new Promise<void>((r) => client.once('clientReady', () => r()));
  await client.login(cfg.token);
  await ready;
  if (process.env.VOICE_DEBUG) client.on('raw', (p: { t?: string }) => p.t?.startsWith('VOICE') && log('raw', p.t));
  log('gateway ready');
  const guild = await client.guilds.fetch(cfg.guildId);
  const connection = joinVoiceChannel({
    channelId: cfg.channelId,
    guildId: cfg.guildId,
    adapterCreator: guild.voiceAdapterCreator,
    selfDeaf: false,
    debug: !!process.env.VOICE_DEBUG,
  });
  connection.on('stateChange', (o, n) => log('voice state:', o.status, '→', n.status));
  if (process.env.VOICE_DEBUG) connection.on('debug', (m) => log('voice debug:', m));
  await entersState(connection, VoiceConnectionStatus.Ready, 30_000);
  connection.subscribe(player);
  outbox.start();
  log(`ready: ${cfg.agentName} is in the voice channel`);

  const active = new Set<string>();
  connection.receiver.speaking.on('start', (userId) => {
    if (userId !== cfg.userId) return;
    if (active.has(userId)) return;
    active.add(userId);
    const opus = connection.receiver.subscribe(userId, { end: { behavior: EndBehaviorType.AfterSilence, duration: SILENCE_MS } });
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
