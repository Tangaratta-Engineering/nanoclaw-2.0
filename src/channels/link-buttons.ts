/**
 * LOCAL CUSTOMIZATION (not part of upstream NanoClaw) — see docs/local-customizations.md.
 *
 * Turn the links in an agent's reply into tappable link buttons (Discord). A bare URL pasted into text is
 * often not tappable (colons, commas and trailing punctuation confuse auto-linking) and is easy to miss;
 * a button always works. Pure functions: the bridge decides when to use the result.
 *
 * Rules: 1-5 distinct links become buttons; 0 or more than 5 (a list of references) leave the text alone.
 * Links inside code are ignored. The URLs are removed from the text (their button replaces them), and a line
 * that was only "Label: <url>" disappears. Markdown links keep their label as the button label.
 */

export interface LinkButton {
  label: string;
  url: string;
}

export interface LinkCardParts {
  text: string;
  buttons: LinkButton[];
}

const MAX_BUTTONS = 5;
const MAX_TEXT = 3800; // Discord embed description limit is 4096; leave headroom
const MD_LINK = /\[([^\]\n]{1,200})\]\((https?:\/\/[^\s)]+)\)/g;
const ANGLE_LINK = /<(https?:\/\/[^\s>]+)>/g;
const BARE_LINK = /https?:\/\/[^\s<>[\]()]+(?:\([^\s)]*\)[^\s<>[\]()]*)*/g;

function hostLabel(url: string): string {
  try {
    const u = new URL(url);
    const host = u.hostname.replace(/^www\./, '');
    if (host === 'mail.google.com') return 'Open email';
    if (host === 'calendar.google.com') return 'Open calendar';
    if (host.endsWith('notion.so') || host.endsWith('notion.com')) return 'Open Notion page';
    if (host === 'github.com') return 'Open on GitHub';
    return `Open ${host}`;
  } catch {
    return 'Open link';
  }
}

function trimUrl(url: string): string {
  // drop trailing punctuation that belongs to the sentence, keeping balanced brackets
  let u = url;
  for (;;) {
    const last = u[u.length - 1];
    if (last && '.,;:!?\'"'.includes(last)) u = u.slice(0, -1);
    else break;
  }
  return u;
}

/** Split into code and non-code segments so links inside code are never touched. */
function segments(text: string): Array<{ code: boolean; s: string }> {
  const out: Array<{ code: boolean; s: string }> = [];
  const re = /```[\s\S]*?```|`[^`\n]*`/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push({ code: false, s: text.slice(last, m.index) });
    out.push({ code: true, s: m[0] });
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push({ code: false, s: text.slice(last) });
  return out;
}

export function extractLinkButtons(input: string): LinkCardParts | null {
  if (!input || !/https?:\/\//.test(input) || input.length > MAX_TEXT) return null;
  const buttons: LinkButton[] = [];
  const seen = new Set<string>();
  const add = (url: string, label?: string): void => {
    if (seen.has(url)) return;
    seen.add(url);
    buttons.push({ label: (label || hostLabel(url)).slice(0, 80), url });
  };

  const body = segments(input)
    .map(({ code, s }) => {
      if (code) return s;
      return s
        .replace(MD_LINK, (_m, label: string, url: string) => {
          add(trimUrl(url), label.trim());
          return label.trim();
        })
        .replace(ANGLE_LINK, (_m, url: string) => {
          add(trimUrl(url));
          return '';
        })
        .replace(BARE_LINK, (m) => {
          const url = trimUrl(m);
          add(url);
          return '' + m.slice(url.length); // keep any trailing sentence punctuation we trimmed
        });
    })
    .join('');

  if (buttons.length === 0 || buttons.length > MAX_BUTTONS) return null;

  // A line that only introduced the link ("Link:", "Cart:", "Here's the cart:") has nothing left to say.
  const introOnly = (line: string): boolean => {
    const bare = line
      .replace(/^[\s>*\-•\d.)]+/, '')
      .replace(/[*_]/g, '')
      .trim();
    return /^(?:link|url|cart|here(?:'s| is)\b.{0,30}):$/i.test(bare);
  };
  const lines = body
    .split('\n')
    .map((l) =>
      l
        .replace(/[ \t]+/g, ' ')
        .replace(/\s+([.,;:!?])/g, '$1')
        .trimEnd(),
    )
    .filter((l) => !introOnly(l));
  const text = lines
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
  return { text: text || 'Tap to open:', buttons };
}
