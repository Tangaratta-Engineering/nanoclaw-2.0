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
const HALLUCINATIONS = ['you', 'thank you', 'thanks for watching', 'bye', 'thank you for watching', 'okay', 'oh', 'um', 'uh', 'hmm', 'mm', 'ah'];

/** Noise to ignore: nothing intelligible, a known hallucination, or (while she is talking) anything uncertain or one word. */
export function isNoise(text: string, reliability: string, whileSpeaking: boolean): boolean {
  const n = norm(text);
  if (!n || n.length < 2) return true;
  if (HALLUCINATIONS.includes(n)) return true;
  if (whileSpeaking && (reliability !== 'good' || n.split(' ').length < 3)) return true;
  return false;
}

/** Short spoken version of a reply: up to two sentences / ~280 chars; the rest is in the text chat. */
export function voiceSummary(text: string, max = 280): string {
  const clean = text.replace(/\s+/g, ' ').trim();
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
