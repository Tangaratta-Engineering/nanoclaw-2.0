import { describe, expect, it } from 'vitest';

import { extractLinkButtons } from './link-buttons.js';

describe('extractLinkButtons', () => {
  it('turns a bare URL into a button and removes it from the text', () => {
    const r = extractLinkButtons(
      'Your cart is ready.\nhttps://au.whogivesacrap.org/cart/42131445219397:2,42131452690501:2',
    )!;
    expect(r.buttons).toEqual([
      {
        label: 'Open au.whogivesacrap.org',
        url: 'https://au.whogivesacrap.org/cart/42131445219397:2,42131452690501:2',
      },
    ]);
    expect(r.text).toBe('Your cart is ready.');
  });

  it('uses the label of a markdown link and keeps it in the sentence', () => {
    const r = extractLinkButtons('Book it here: [Sunset Villa page](https://example.com/villa) before Friday.')!;
    expect(r.buttons).toEqual([{ label: 'Sunset Villa page', url: 'https://example.com/villa' }]);
    expect(r.text).toBe('Book it here: Sunset Villa page before Friday.');
  });

  it('does not swallow sentence punctuation or brackets', () => {
    const r = extractLinkButtons('See (https://example.com/a), then https://example.com/b.')!;
    expect(r.buttons.map((b) => b.url)).toEqual(['https://example.com/a', 'https://example.com/b']);
    expect(r.text).toBe('See (), then.');
  });

  it('drops a line that only introduced the link', () => {
    const r = extractLinkButtons('Receipt below\nLink: https://example.com/r\nThanks')!;
    expect(r.text).toBe('Receipt below\nThanks');
  });

  it('gives friendly labels for common hosts and dedupes repeated links', () => {
    const r = extractLinkButtons(
      'https://mail.google.com/mail/u/0/#inbox/abc and again https://mail.google.com/mail/u/0/#inbox/abc plus https://www.notion.so/page-123',
    )!;
    expect(r.buttons).toEqual([
      { label: 'Open email', url: 'https://mail.google.com/mail/u/0/#inbox/abc' },
      { label: 'Open Notion page', url: 'https://www.notion.so/page-123' },
    ]);
  });

  it('leaves messages alone when there are no links, too many links, or the links are in code', () => {
    expect(extractLinkButtons('no links here')).toBeNull();
    expect(extractLinkButtons(Array.from({ length: 6 }, (_, i) => `https://example.com/${i}`).join('\n'))).toBeNull();
    expect(extractLinkButtons('Run `curl https://example.com/x` and\n```\nhttps://example.com/y\n```')).toBeNull();
  });

  it('leaves very long messages alone', () => {
    expect(extractLinkButtons('x'.repeat(3900) + ' https://example.com')).toBeNull();
  });

  it('falls back to a short prompt when only links were sent', () => {
    const r = extractLinkButtons('https://example.com/only')!;
    expect(r.text).toBe('Tap to open:');
    expect(r.buttons).toHaveLength(1);
  });
});
