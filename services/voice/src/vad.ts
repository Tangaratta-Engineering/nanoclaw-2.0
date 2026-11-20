/**
 * Deciding when George has stopped talking from the audio itself. Discord keeps sending packets for as long as his
 * phone hears ANY noise (a car, a fan), and the receive stream only ends after 1.3 s without packets, so in a noisy
 * place a clip never ends and nothing is sent until he mutes. Here a clip ends after `silenceMs` without anything
 * louder than the background, whether or not packets keep arriving, and a clip that never contains speech is dropped
 * without the send gate ever hearing about it.
 */

/** Tracks the background level: falls quickly to a quiet frame, creeps up slowly so speech does not raise it much. */
export class NoiseFloor {
  private level: number;
  private down: number;
  private up: number;
  constructor(initial = 0.003, down = 0.05, up = 0.0005) {
    this.level = initial;
    this.down = down;
    this.up = up;
  }
  update(rms: number): void {
    this.level += (rms - this.level) * (rms < this.level ? this.down : this.up);
  }
  get value(): number {
    return this.level;
  }
}

export interface VadConfig {
  /** A frame counts as speech above max(minVoiceRms, floor * floorMult). */
  minVoiceRms: number;
  floorMult: number;
  /** Speech heard (in total) before the clip counts as speech. */
  startVoicedMs: number;
  /** Quiet this long after speech ends the clip. */
  silenceMs: number;
  /** A clip with no speech in this long is dropped as noise. */
  noiseClipMs: number;
  /** Safety: a clip never runs longer than this. */
  maxClipMs: number;
}

export const DEFAULT_VAD: VadConfig = { minVoiceRms: 0.012, floorMult: 3, startVoicedMs: 160, silenceMs: 1300, noiseClipMs: 1200, maxClipMs: 45_000 };

export type VadEvent = 'continue' | 'speech-start' | 'end-speech' | 'end-noise';

export class ClipVad {
  private age = 0;
  private quiet = 0;
  private voiced = 0;
  private started = false;
  private cfg: VadConfig;
  private floor: NoiseFloor;
  constructor(cfg: VadConfig, floor: NoiseFloor) {
    this.cfg = cfg;
    this.floor = floor;
  }

  /** Feed one frame's level (`ms` of audio). */
  push(rms: number, ms: number): VadEvent {
    const threshold = Math.max(this.cfg.minVoiceRms, this.floor.value * this.cfg.floorMult);
    const loud = rms > threshold;
    this.floor.update(rms);
    this.age += ms;
    if (loud) {
      this.voiced += ms;
      this.quiet = 0;
    } else {
      this.quiet += ms;
    }
    if (!this.started && this.voiced >= this.cfg.startVoicedMs) {
      this.started = true;
      return 'speech-start';
    }
    if (this.age >= this.cfg.maxClipMs) return this.started ? 'end-speech' : 'end-noise';
    if (this.started && this.quiet >= this.cfg.silenceMs) return 'end-speech';
    if (!this.started && this.age >= this.cfg.noiseClipMs) return 'end-noise';
    return 'continue';
  }

  get voicedMs(): number {
    return this.voiced;
  }
  get ageMs(): number {
    return this.age;
  }
  get isSpeech(): boolean {
    return this.started;
  }
  /** Milliseconds of audio at the end that were quiet (the tail to trim before transcribing). */
  get trailingQuietMs(): number {
    return this.quiet;
  }
}

/** RMS level 0..1 of 48 kHz stereo s16le audio. */
export function frameRms(pcm: Buffer): number {
  const n = Math.floor(pcm.length / 2);
  if (!n) return 0;
  let sum = 0;
  for (let i = 0; i < n; i++) {
    const v = pcm.readInt16LE(i * 2);
    sum += v * v;
  }
  return Math.sqrt(sum / n) / 32768;
}

/** Milliseconds of audio in a 48 kHz stereo s16le buffer. */
export const pcmMs = (pcm: Buffer): number => pcm.length / 192;
