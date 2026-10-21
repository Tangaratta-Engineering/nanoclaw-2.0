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
