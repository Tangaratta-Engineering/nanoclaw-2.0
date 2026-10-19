/**
 * Guards the local second-Discord-bot customization (see docs/local-customizations.md):
 * importing the channel barrel must register the "discord-timmy" adapter alongside the
 * default "discord" one. Fails loudly if an upgrade drops the barrel import.
 */
import { describe, it, expect } from 'vitest';

import { getRegisteredChannelNames } from './channel-registry.js';
import './index.js';

describe('discord-timmy channel registration', () => {
  it('registers discord-timmy via the channel barrel without disturbing the default bot', () => {
    const names = getRegisteredChannelNames();
    expect(names).toContain('discord');
    expect(names).toContain('discord-timmy');
  });
});
