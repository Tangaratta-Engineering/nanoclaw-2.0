import path from 'node:path';

export interface Config {
  token: string;
  guildId: string;
  channelId: string;
  /** Discord user whose voice is listened to (everyone else is ignored). */
  userId: string;
  /** Name used for the agent's voice and the spoken-call preamble. */
  agentName: string;
  /** OneCLI agent identifier used to inject the Groq key. */
  onecliAgent: string;
  /** Where the agent's replies come from / go: the DM messaging group. */
  dmPlatformId: string;
  /** Adapter instance of the bot (omit for the default bot). */
  instance?: string;
  socketPath: string;
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

export function loadConfig(root = path.resolve(import.meta.dirname, '../../..')): Config {
  return {
    token: process.env.VOICE_BOT_TOKEN || need('DISCORD_BOT_TOKEN'),
    guildId: need('VOICE_GUILD_ID'),
    channelId: need('VOICE_CHANNEL_ID'),
    userId: need('VOICE_USER_ID'),
    agentName: process.env.VOICE_AGENT_NAME || 'Tiff',
    onecliAgent: need('VOICE_ONECLI_AGENT'),
    dmPlatformId: need('VOICE_DM_PLATFORM_ID'),
    instance: process.env.VOICE_INSTANCE || undefined,
    socketPath: process.env.VOICE_SOCKET || path.join(root, 'data/cli.sock'),
    skillsDir: path.join(root, 'container/skills'),
    agentImage: need('VOICE_AGENT_IMAGE'),
    voiceId: process.env.VOICE_VOICE_ID || 'en_US-hfc_female-medium',
    piperHome: process.env.PIPER_HOME || path.join(process.env.HOME ?? '', 'projects/.nanoclaw-tools/piper'),
  };
}
