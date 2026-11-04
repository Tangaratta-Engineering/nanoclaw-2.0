/** Conversation rules for the live call. Pure functions so they can be tested. */

const STOP_PHRASES = [
  'stop', 'stop talking', 'be quiet', 'quiet', 'shut up', 'enough', 'hold on', 'wait', 'pause', 'cancel', 'never mind', 'nevermind', 'okay stop', 'ok stop', 'tiff stop', 'timmy stop',
];

const norm = (t: string) => t.toLowerCase().replace(/[^a-z\s']/g, ' ').replace(/\s+/g, ' ').trim();

const STOP_NAMES = ['tiff', 'tiffany', 'timmy', 'timmie', 'tim', 'jimmy', 'jimmie', 'jim', 'jack'];
const STOP_FILLER = ['please', 'okay', 'ok', 'now', 'just', 'hey', 'hi', 'sorry', 'yeah', 'yes', 'no', 'right'];

/**
 * A short utterance that is (or starts with) a stop word. Longer sentences containing "stop" are not commands.
 * Names ("Tiff, Tiff, stop"), filler ("stop, please") and repeats ("stop stop stop stop") are ignored first,
 * because that is how people actually shout it at someone who keeps talking.
 */
export function isStopCommand(text: string, names: readonly string[] = []): boolean {
  const drop = new Set([...STOP_NAMES, ...names.map((x) => x.toLowerCase()), ...STOP_FILLER]);
  const collapsed: string[] = [];
  for (const w of norm(text).split(' ')) {
    if (!w || drop.has(w) || collapsed[collapsed.length - 1] === w) continue;
    collapsed.push(w);
  }
  if (!collapsed.length || collapsed.length > 4) return false;
  const n = collapsed.join(' ');
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

/** Speakable version of a reply: code spans removed; very long replies are cut at a sentence end (default ~1,600 characters, about 100 s of speech) with a pointer to the chat. */
export function voiceSummary(text: string, max = 1600): string {
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

export type AgentKey = 'tiff' | 'jimmy' | 'jack';

/** The words George uses for each agent (including what speech-to-text makes of them). */
const AGENT_WORDS: Record<AgentKey, string[]> = {
  tiff: ['tiff', 'tiffany'],
  jimmy: ['jimmy', 'jimmie', 'jim', 'timmy', 'timmie', 'tim', 'timothy'],
  jack: ['jack', 'jak', 'jacques'],
};

/** Which agent a name word refers to (repeated letters ignored), or null. */
export function agentKeyOf(word: string): AgentKey | null {
  const f = word.toLowerCase().replace(/(.)\1+/g, '$1');
  for (const [key, words] of Object.entries(AGENT_WORDS) as [AgentKey, string[]][]) {
    if (words.some((w) => w.replace(/(.)\1+/g, '$1') === f)) return key;
  }
  return null;
}

/** Every agent name George uses, so "Tiff, Timmy, your turn" is read as addressing both. */
const AGENT_NAMES = ['tiff', 'tiffany', 'timmy', 'timmie', 'tim', 'jimmy', 'jimmie', 'jim', 'timothy', 'jack', 'jak', 'jacques'];
const DEFAULT_AGENT_NAMES = ['tiff', 'tiffany'];

/** "timmmy" and "timmy" are the same word to speech-to-text. */
const fold = (w: string) => w.replace(/(.)\1+/g, '$1');

/**
 * The agent names at the start of an utterance, folded: ("Hey Tiff, Timmy, ..." -> [tiff, timy]).
 * Greetings are skipped only before the first name; the run stops at the first ordinary word.
 */
function leadingAddress(text: string, known: Set<string>): string[] {
  const out: string[] = [];
  let greetings = 0;
  for (const w of norm(text).split(' ').filter(Boolean).slice(0, 7)) {
    if (!out.length && GREETINGS.has(w) && greetings < 2) {
      greetings++;
      continue;
    }
    const f = fold(w);
    if (!known.has(f)) break;
    out.push(f);
  }
  return out;
}

/** True when one of `names` is among the names that open the utterance ("Hey Timmy, ..." / "Tiff, Timmy: ..."). */
export function startsWithName(text: string, names: string[]): boolean {
  if (!names.length) return false;
  const mine = new Set(names.map(fold));
  const run = leadingAddress(text, new Set([...AGENT_NAMES.map(fold), ...mine]));
  return run.some((n) => mine.has(n));
}

/**
 * Is this utterance for this agent? A named agent answers when its name opens the utterance (alone or among
 * several: "Tiff, Timmy, your turn"). The default agent answers anything not addressed to another agent, and
 * anything that includes its own name.
 */
export function isForMe(text: string, wakeNames: string[], otherNames: string[]): boolean {
  if (wakeNames.length) return startsWithName(text, wakeNames);
  const others = new Set(otherNames.map(fold));
  const run = leadingAddress(text, new Set([...AGENT_NAMES.map(fold), ...others]));
  if (run.some((n) => DEFAULT_AGENT_NAMES.map(fold).includes(n))) return true;
  return !run.some((n) => others.has(n));
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

// Words a sentence cannot end on: if the transcript stops on one, the speaker is mid-thought.
const OPEN_ENDINGS = new Set(['and', 'but', 'so', 'because', 'then', 'or', 'like', 'um', 'uh', 'er', 'well', 'the', 'a', 'an', 'to', 'of', 'with', 'that', 'which', 'if', 'when', 'my', 'is', 'are', 'was', 'i', 'it', 'for', 'on', 'in', 'at', 'also', 'plus', 'as', 'about', 'what', 'how', 'where', 'who']);

/**
 * How long to wait for a continuation after a transcript. A pause that sounds unfinished
 * (trailing "...", a comma, a dangling "and", only a word or two) gets a long wait; a complete
 * sentence a shorter one; a long passage a little longer because speakers tend to continue.
 */
export function debounceFor(text: string): number {
  const t = text.trim();
  const words = t.split(/\s+/).filter(Boolean);
  const last = (words[words.length - 1] ?? '').toLowerCase().replace(/[^a-z']/g, '');
  if (/(\.{2,}|…|[,;:\u2014-])["')]*$/.test(t)) return 4500;
  if (words.length <= 3) return 4000;
  if (OPEN_ENDINGS.has(last)) return 4500;
  if (/\?["')]*$/.test(t) && words.length >= 4) return 1500; // a clear question: not much more is coming
  if (/[.?!]["')]*$/.test(t)) return words.length >= 25 ? 3000 : 2000;
  return 3500;
}

/**
 * Who is this utterance addressed to? Names that open it ("Jack, ..." / "Hey Tiff, Jimmy, your turn"), else a name that
 * closes a short one ("You still there, Jack?"). Anything else, including a name mentioned in the middle of a
 * sentence ("I changed Jimmy's name"), is not an address and returns [].
 */
export function addressees(text: string): AgentKey[] {
  const words = norm(text).split(' ').filter(Boolean);
  const out: AgentKey[] = [];
  const add = (w: string) => {
    const k = agentKeyOf(w);
    if (k && !out.includes(k)) out.push(k);
  };
  let greetings = 0;
  let i = 0;
  for (; i < Math.min(words.length, 7); i++) {
    const w = words[i];
    if (!out.length && GREETINGS.has(w) && greetings < 2) {
      greetings++;
      continue;
    }
    if (!agentKeyOf(w)) break;
    add(w);
  }
  if (out.length) return out;
  if (words.length >= 2 && words.length <= 12) {
    const last = words[words.length - 1];
    if (agentKeyOf(last)) add(last);
  }
  return out;
}

/** A short thing to say while the agent is still working on an answer, so a long wait is not silence. */
const FILLERS: Record<AgentKey, string[]> = {
  tiff: ['One moment.', 'Let me check.', 'Just a sec.'],
  jimmy: ['One moment.', 'Let me look into that.'],
  jack: ['Let me look into that.', 'One moment.'],
};
export function fillerFor(key: AgentKey, n: number): string {
  const list = FILLERS[key];
  return list[Math.abs(n) % list.length];
}
