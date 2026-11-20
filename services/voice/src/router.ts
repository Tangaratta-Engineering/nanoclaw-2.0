import { AddresseeState } from './addressee.ts';
import type { AgentKey } from './policy.ts';

/**
 * Who an utterance goes to when ONE service listens for the whole call. Named: whoever is named. Unnamed: whoever
 * George was last talking to, else the default agent (Tiff). The same rules `isForAgent` applies per service,
 * decided once.
 */
export function routeTargets(named: AgentKey[], state: AddresseeState, now: number = Date.now()): AgentKey[] {
  if (named.length) {
    state.remember(named, now);
    return named;
  }
  const current = state.current(now);
  if (current.length) {
    state.remember(current, now); // the conversation continues: keep it alive
    return current;
  }
  return ['tiff'];
}
