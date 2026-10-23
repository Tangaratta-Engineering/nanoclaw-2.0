import { debounceFor } from './policy.ts';

/**
 * Decides when what George said is sent to the agent. Nothing is sent while he is speaking or while a clip is
 * still being transcribed; the wait restarts after every clip and is longer when the speech sounds unfinished.
 */
export class SendGate {
  private onSend: (text: string) => void;
  private patience: number;
  private buf: string[] = [];
  private timer: NodeJS.Timeout | null = null;
  private capturing = 0;
  private transcribing = 0;
  private holdMs = 2000;

  constructor(onSend: (text: string) => void, patience = 1) {
    this.onSend = onSend;
    this.patience = patience;
  }

  /** He started talking: cancel any pending send. */
  captureStart(): void {
    this.capturing++;
    this.clear();
  }

  /** The clip ended (call `transcribeStart` first so there is no gap). */
  captureEnd(): void {
    if (this.capturing > 0) this.capturing--;
    this.arm();
  }

  transcribeStart(): void {
    this.transcribing++;
    this.clear();
  }

  transcribeEnd(): void {
    if (this.transcribing > 0) this.transcribing--;
    this.arm();
  }

  /** A real transcript to send. */
  add(text: string): void {
    this.buf.push(text);
    this.holdMs = debounceFor(text);
  }

  /** A filler or breath while composing a thought: keep waiting a bit longer. */
  filler(): void {
    if (this.buf.length) this.holdMs = Math.max(this.holdMs, 3000);
  }

  /** Drop everything (sleep, leaving the channel). */
  reset(): void {
    this.buf = [];
    this.capturing = 0;
    this.clear();
  }

  pendingText(): string {
    return this.buf.join(' ').trim();
  }

  private clear(): void {
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
  }

  private arm(): void {
    this.clear();
    if (!this.buf.length || this.capturing || this.transcribing) return;
    this.timer = setTimeout(() => {
      this.timer = null;
      if (this.capturing || this.transcribing) return;
      const text = this.buf.splice(0).join(' ').trim();
      if (text) this.onSend(text);
    }, this.holdMs * this.patience);
  }
}
