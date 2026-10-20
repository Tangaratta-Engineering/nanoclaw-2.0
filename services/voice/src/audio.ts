/** PCM helpers: Discord gives 48 kHz stereo s16le; Whisper wants 16 kHz mono. */

export function toMono16k(pcm48kStereo: Buffer): Int16Array {
  const frames = Math.floor(pcm48kStereo.length / 4);
  const out = new Int16Array(Math.floor(frames / 3));
  for (let i = 0; i < out.length; i++) {
    let sum = 0;
    for (let k = 0; k < 3; k++) {
      const o = (i * 3 + k) * 4;
      sum += pcm48kStereo.readInt16LE(o) + pcm48kStereo.readInt16LE(o + 2);
    }
    out[i] = Math.round(sum / 6);
  }
  return out;
}

export function wav16kMono(samples: Int16Array): Buffer {
  const data = Buffer.from(samples.buffer, samples.byteOffset, samples.byteLength);
  const h = Buffer.alloc(44);
  h.write('RIFF', 0);
  h.writeUInt32LE(36 + data.length, 4);
  h.write('WAVEfmt ', 8);
  h.writeUInt32LE(16, 16);
  h.writeUInt16LE(1, 20); // PCM
  h.writeUInt16LE(1, 22); // mono
  h.writeUInt32LE(16000, 24);
  h.writeUInt32LE(32000, 28);
  h.writeUInt16LE(2, 32);
  h.writeUInt16LE(16, 34);
  h.write('data', 36);
  h.writeUInt32LE(data.length, 40);
  return Buffer.concat([h, data]);
}

export function durationSecs(samples: Int16Array): number {
  return samples.length / 16000;
}

/** RMS level 0..1 — used to drop clips that are only background noise. */
export function rms(samples: Int16Array): number {
  if (!samples.length) return 0;
  let s = 0;
  for (const v of samples) s += v * v;
  return Math.sqrt(s / samples.length) / 32768;
}
