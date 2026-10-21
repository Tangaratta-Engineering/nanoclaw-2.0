import path from 'node:path';

export interface Config {
  token: string;
  guildId: string;
  channelId: string;
  /** Discord user whose voice is listened to (everyone else is ignored). */
  userId: string;
  /** Name used for the agent's voice and the spoken-call preamble. */
  agentName: string;
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
}

function need(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`missing env ${name}`);
  return v;
}

const list = (v?: string): string[] => (v ?? '').split(',').map((x) => x.trim().toLowerCase()).filter(Boolean);

export function loadConfig(root = path.resolve(import.meta.dirname, '../../..')): Config {
  return {
    token: process.env.VOICE_BOT_TOKEN || need(process.env.VOICE_TOKEN_VAR || 'DISCORD_BOT_TOKEN'),
    guildId: need('VOICE_GUILD_ID'),
    channelId: need('VOICE_CHANNEL_ID'),
    userId: need('VOICE_USER_ID'),
    agentName: process.env.VOICE_AGENT_NAME || 'Tiff',
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
  };
}
