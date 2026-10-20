import { execFile } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { promisify } from 'node:util';

import { wav16kMono } from './audio.ts';
import type { Config } from './config.ts';

const run = promisify(execFile);

export interface Transcript {
  text: string;
  reliability: string;
}

/** Transcribe via the transcribe skill, with Groq's key injected by the OneCLI gateway. */
export async function transcribe(cfg: Config, samples: Int16Array): Promise<Transcript> {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'voice-'));
  const file = path.join(dir, 'utt.wav');
  fs.writeFileSync(file, wav16kMono(samples));
  try {
    const { stdout } = await run(
      'onecli',
      ['run', '--agent', cfg.onecliAgent, '--', 'python3', path.join(cfg.skillsDir, 'transcribe/scripts/transcribe.py'), '--engine', 'cloud', file],
      { timeout: 30_000, maxBuffer: 1 << 20 },
    );
    return parseTranscribe(stdout);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

export function parseTranscribe(out: string): Transcript {
  const lines = out.split('\n').filter((l) => !l.startsWith('onecli:'));
  const header = lines.find((l) => l.startsWith('[engine=')) ?? '';
  const reliability = /reliability=(\w+)/.exec(header)?.[1] ?? 'unknown';
  const text = lines
    .filter((l) => l !== header && !/^(note|reliability warnings|alternative)/i.test(l.trim()))
    .join(' ')
    .replace(/\s+/g, ' ')
    .trim();
  return { text, reliability };
}
