/** Conversation rules for the live call. Pure functions so they can be tested. */

const STOP_PHRASES = [
  'stop', 'stop talking', 'be quiet', 'quiet', 'shut up', 'enough', 'hold on', 'wait', 'pause', 'cancel', 'never mind', 'nevermind', 'okay stop', 'ok stop', 'tiff stop', 'timmy stop',
];

const norm = (t: string) => t.toLowerCase().replace(/[^a-z\s']/g, ' ').replace(/\s+/g, ' ').trim();

/** A short utterance that is (or starts with) a stop word. Longer sentences containing "stop" are not commands. */
export function isStopCommand(text: string): boolean {
  const n = norm(text);
  if (!n) return false;
  const words = n.split(' ');
  if (words.length > 4) return false;
  return STOP_PHRASES.some((p) => n === p || n.startsWith(p + ' ') || n.endsWith(' ' + p));
}

// Whisper tends to invent these from silence or background noise.
const HALLUCINATION_PATTERNS = [/subtitles? by/, /amara\.org/, /thanks? for watching/, /please subscribe/, /see you (in the )?next/, /transcribed by/, /^bye( bye)?$/];
const HALLUCINATIONS = ['you', 'thank you', 'thanks for watching', 'bye', 'thank you for watching', 'okay', 'oh', 'um', 'uh', 'hmm', 'mm', 'ah'];

/** Noise to ignore: nothing intelligible, a known hallucination, or (while she is talking) anything uncertain or one word. */
export function isNoise(text: string, reliability: string, whileSpeaking: boolean): boolean {
  const n = norm(text);
  if (!n || n.length < 2) return true;
  if (HALLUCINATIONS.includes(n) || HALLUCINATION_PATTERNS.some((r) => r.test(n))) return true;
  if (whileSpeaking && (reliability !== 'good' || n.split(' ').length < 3)) return true;
  return false;
}

/** Short spoken version of a reply: up to two sentences / ~280 chars; the rest is in the text chat. */
export function voiceSummary(text: string, max = 280): string {
  // Code spans (file paths, commands) are not speakable: drop them.
  const clean = text.replace(/`[^`]*`/g, '').replace(/\s+/g, ' ').replace(/\s+([.,;:!?])/g, '$1').trim();
  if (clean.length <= max) return clean;
  const sentences = clean.match(/[^.!?]+[.!?]+(\s|$)/g) ?? [clean];
  let out = '';
  for (const s of sentences) {
    if ((out + s).length > max && out) break;
    out += s;
    if (out.length >= max) break;
  }
  out = out.trim().slice(0, max);
  return out + ' The rest is in the chat.';
}

/** True when George asked for something to be read out in full, so the spoken limit is raised. */
export function wantsFullReadout(utterance: string): boolean {
  return /\bread\b.*\b(out|back|to me|aloud)\b|\bgo through\b|\btell me everything\b|\ball of (it|them)\b/i.test(utterance);
}

/** An intro line that only announces something else ("Added to the file:") is not worth speaking. */
export function isLeadIn(text: string): boolean {
  return /:\s*$/.test(text.trim());
}

const GREETINGS = new Set(['hey', 'hi', 'hello', 'ok', 'okay', 'yo', 'oi', 'um', 'uh', 'so']);

/** True when the first few words of the utterance are one of `names` ("Hey Timmy, ..." / "Timmy: ..."). */
export function startsWithName(text: string, names: string[]): boolean {
  if (!names.length) return false;
  const words = norm(text).split(' ').filter(Boolean);
  let i = 0;
  while (i < words.length && i < 2 && GREETINGS.has(words[i])) i++;
  return words.slice(i, i + 1).some((w) => names.includes(w));
}

/**
 * Should this service act on the utterance? A named agent answers only when addressed by name;
 * the default agent answers everything not addressed to another agent.
 */
export function isForMe(text: string, wakeNames: string[], otherNames: string[]): boolean {
  if (wakeNames.length) return startsWithName(text, wakeNames);
  return !startsWithName(text, otherNames);
}

const SLEEP_PHRASES = ['go to sleep', 'sleep now', 'stop listening', 'mute', 'mute yourself', 'go quiet', 'hang up', 'goodnight'];

/** "Go to sleep" / "stop listening": a short utterance containing a sleep phrase. Applies to every agent in the call. */
export function isSleepCommand(text: string): boolean {
  const n = norm(text);
  if (!n || n.split(' ').length > 6) return false;
  return SLEEP_PHRASES.some((p) => n === p || n.includes(' ' + p) || n.startsWith(p + ' ') || n.endsWith(' ' + p));
}

export interface Presence {
  /** George is in the call channel right now. */
  georgeInChannel: boolean;
  /** The bot currently holds a (non-destroyed) voice connection. */
  connected: boolean;
  /** A leave is already scheduled. */
  leaving: boolean;
}

/** What the lifecycle loop should do: join when George is there, leave (after a grace period) when he is not. */
export function lifecycleAction(p: Presence): 'join' | 'schedule-leave' | 'cancel-leave' | 'none' {
  if (p.georgeInChannel) {
    if (!p.connected) return 'join';
    return p.leaving ? 'cancel-leave' : 'none';
  }
  return p.connected && !p.leaving ? 'schedule-leave' : 'none';
}

/** Split a reply into speakable chunks so the first can play while the rest is still being synthesized. */
export function splitForSpeech(text: string, minLen = 40): string[] {
  const parts = text.replace(/\s+/g, ' ').trim().match(/[^.!?]+[.!?]*\s*/g) ?? [text];
  const out: string[] = [];
  let cur = '';
  for (const p of parts) {
    cur += p;
    if (cur.trim().length >= minLen) {
      out.push(cur.trim());
      cur = '';
    }
  }
  if (cur.trim()) {
    if (out.length && cur.trim().length < 15) out[out.length - 1] += ' ' + cur.trim();
    else out.push(cur.trim());
  }
  return out;
}

/** How long to wait for a continuation after a transcript: short when it sounds finished, longer when it trails off. */
export function debounceFor(text: string): number {
  const t = text.trim();
  const words = t.split(/\s+/).length;
  if (/[.?!]["')]*$/.test(t) && words >= 3) return 1000;
  return 2000;
}
