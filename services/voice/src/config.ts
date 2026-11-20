import path from 'node:path';

import { agentKeyOf, type AgentKey } from './policy.ts';

export interface Config {
  token: string;
  guildId: string;
  channelId: string;
  /** Discord user whose voice is listened to (everyone else is ignored). */
  userId: string;
  /** Name used for the agent's voice and the spoken-call preamble. */
  agentName: string;
  /** A word that, ending a message, sends it at once ("... over"). Empty = off. */
  endWord: string;
  /** Which of the three agents this service speaks for (derived from the agent name). */
  agentKey: AgentKey;
  /** Shared file recording who George is talking to (all voice services use the same one). */
  addresseeFile: string;
  floorFile: string;
  spokenFile: string;
  /** Names this agent answers to when addressed ("Timmy, ..."). Empty = default agent that answers anything not addressed to another. */
  wakeNames: string[];
  /** Names of the other agents; an utterance addressed to one of them is ignored by this service. */
  otherNames: string[];
  /** OneCLI agent identifier used to inject the Groq key. */
  onecliAgent: string;
  /** Where the agent's replies come from / go: the DM messaging group. */
  dmPlatformId: string;
  /** Adapter instance of the bot (omit for the default bot). */
  instance?: string;
  socketPath: string;
  /** The agent group's session directory (contains <session>/outbound.db). */
  sessionsDir: string;
  skillsDir: string;
  agentImage: string;
  voiceId: string;
  piperHome: string;
  /** Google Chirp 3 HD voice for this agent (e.g. en-US-Chirp3-HD-Aoede). Unset = Piper only. Piper is always the fallback. */
  googleVoice?: string;
  /** Shared monthly character counter (the `speak` skill writes the same file from inside the agent containers). */
  googleUsageFile: string;
  /** Speech-to-text for live calls: Groq Whisper (default) or Google Cloud (opt-in). Google falls back to Groq, then local. */
  stt: 'groq' | 'google';
  /** Monthly cap on billed Google speech-to-text minutes; above it calls use Groq until next month. */
  sttGoogleMaxMinutes: number;
  /** Shared monthly counter of billed Google speech-to-text seconds (written by the transcribe skill). */
  sttGoogleUsageFile: string;
}

function need(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`missing env ${name}`);
  return v;
}

const list = (v?: string): string[] => (v ?? '').split(',').map((x) => x.trim().toLowerCase()).filter(Boolean);

function sttEngine(v?: string): 'groq' | 'google' {
  const e = (v || 'groq').trim().toLowerCase();
  if (e !== 'groq' && e !== 'google') throw new Error(`VOICE_STT must be groq or google, not "${e}"`);
  return e;
}

export function loadConfig(root = path.resolve(import.meta.dirname, '../../..')): Config {
  return {
    token: process.env.VOICE_BOT_TOKEN || need(process.env.VOICE_TOKEN_VAR || 'DISCORD_BOT_TOKEN'),
    guildId: need('VOICE_GUILD_ID'),
    channelId: need('VOICE_CHANNEL_ID'),
    userId: need('VOICE_USER_ID'),
    agentName: process.env.VOICE_AGENT_NAME || 'Tiff',
    endWord: (process.env.VOICE_END_WORD ?? 'over').trim().toLowerCase(),
    agentKey: agentKeyOf(process.env.VOICE_AGENT_NAME || 'Tiff') ?? 'tiff',
    spokenFile: process.env.VOICE_SPOKEN_FILE || path.join(process.env.HOME ?? '', 'projects/.nanoclaw-data/voice/spoken.json'),
    floorFile: process.env.VOICE_FLOOR_FILE || path.join(process.env.HOME ?? '', 'projects/.nanoclaw-data/voice/floor.json'),
    addresseeFile: process.env.VOICE_ADDRESSEE_FILE || path.join(process.env.HOME ?? '', 'projects/.nanoclaw-data/voice/addressee.json'),
    wakeNames: list(process.env.VOICE_WAKE_NAMES),
    otherNames: list(process.env.VOICE_OTHER_NAMES),
    onecliAgent: need('VOICE_ONECLI_AGENT'),
    dmPlatformId: need('VOICE_DM_PLATFORM_ID'),
    instance: process.env.VOICE_INSTANCE || undefined,
    sessionsDir: process.env.VOICE_SESSIONS_DIR || path.join(root, 'data/v2-sessions', need('VOICE_ONECLI_AGENT')),
    socketPath: process.env.VOICE_SOCKET || path.join(root, 'data/cli.sock'),
    skillsDir: path.join(root, 'container/skills'),
    agentImage: need('VOICE_AGENT_IMAGE'),
    voiceId: process.env.VOICE_VOICE_ID || 'en_US-hfc_female-medium',
    piperHome: process.env.PIPER_HOME || path.join(process.env.HOME ?? '', 'projects/.nanoclaw-tools/piper'),
    googleVoice: process.env.VOICE_GOOGLE_VOICE || undefined,
    googleUsageFile: process.env.SPEAK_GOOGLE_USAGE || path.join(process.env.HOME ?? '', 'projects/.nanoclaw-data/voice/google-usage.json'),
    stt: sttEngine(process.env.VOICE_STT),
    sttGoogleMaxMinutes: Number(process.env.VOICE_STT_GOOGLE_MAX_MINUTES || '300'),
    sttGoogleUsageFile: process.env.STT_GOOGLE_USAGE || path.join(process.env.HOME ?? '', 'projects/.nanoclaw-data/voice/stt-google-usage.json'),
  };
}
