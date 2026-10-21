import { execFile } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { promisify } from 'node:util';

import type { Config } from './config.ts';

const run = promisify(execFile);

/** Turn text into Opus-in-Ogg using the speak skill inside the agent image (offline). Returns the .ogg path. */
export async function synthesize(cfg: Config, text: string): Promise<string> {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'voice-tts-'));
  fs.chmodSync(dir, 0o777); // container user differs from host user
  await run(
    'docker',
    [
      'run', '--rm', '--network', 'none',
      '-v', `${cfg.skillsDir}:/app/skills:ro`,
      '-v', `${cfg.piperHome}:/piper:ro`,
      '-v', `${dir}:/out`,
      '-e', 'PIPER_HOME=/piper',
      '-e', `ASSISTANT_NAME=${cfg.agentName}`,
      '--entrypoint', '/app/skills/speak/scripts/speak',
      cfg.agentImage,
      '--voice', cfg.voiceId, '--out', '/out/reply.ogg', text,
    ],
    { timeout: 60_000 },
  );
  return path.join(dir, 'reply.ogg');
}
