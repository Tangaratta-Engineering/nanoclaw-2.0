// Recovery for a frozen Peoplecare tab (same approach as services/woolies/recover.mjs). Closing the tab is not
// always enough: a hung Chrome renderer is shared by every tab on the site, so a replacement tab freezes too.
// Escalate: fresh tab (opened on Home: deep links do not work on this site), then restart the claims Chrome.

/**
 * Called when no Peoplecare tab answers. `tryTabs()` resolves to a live connection or null.
 * `restartChrome()` restarts the claims Chrome (the profile keeps the login); `canRestart()` rate-limits it.
 */
export async function recoverTab({ cdp, site, fetchFn = fetch, tryTabs, restartChrome, canRestart, sleep, log = () => {} }) {
  try {
    const targets = await (await fetchFn(`${cdp}/json`)).json();
    for (const t of targets.filter((x) => x.type === 'page' && x.url.includes(site))) await fetchFn(`${cdp}/json/close/${t.id}`).catch(() => {});
    await fetchFn(`${cdp}/json/new?https://${site}/`, { method: 'PUT' });
    await sleep(8000);
    const c = await tryTabs();
    if (c) { log('recovered: replaced the frozen Peoplecare tab'); return c; }
  } catch (e) { log('tab replacement failed:', e.message); }
  if (!canRestart()) throw new Error('the Peoplecare tab is frozen and Chrome was restarted recently: try again in a few minutes');
  log('tab still frozen: restarting the claims Chrome');
  await restartChrome();
  for (let i = 0; i < 12; i++) {
    await sleep(4000);
    try { const c = await tryTabs(); if (c) { log('recovered: claims Chrome restarted'); return c; } } catch { /* Chrome still starting */ }
  }
  throw new Error('the Peoplecare tab is frozen and restarting the claims Chrome did not bring it back');
}
