// Recovery for a frozen Woolworths tab. Closing the tab is not always enough: a hung Chrome renderer is
// shared by every tab on the site, so a replacement tab freezes too. Escalate: fresh tab, then restart Chrome.
const isWoolies = (x) => x.type === 'page' && x.url.includes('woolworths.com.au');

/**
 * Called when no Woolworths tab answers. `tryTabs()` resolves to a live connection or null.
 * `restartChrome()` restarts the server Chrome (profile and sign-in survive); `canRestart()` rate-limits it.
 */
export async function recoverTab({ cdp, fetchFn = fetch, tryTabs, restartChrome, canRestart, sleep, log = () => {} }) {
  try {
    const targets = await (await fetchFn(`${cdp}/json`)).json();
    for (const t of targets.filter(isWoolies)) await fetchFn(`${cdp}/json/close/${t.id}`).catch(() => {});
    await fetchFn(`${cdp}/json/new?https://www.woolworths.com.au/shop/mylists`, { method: 'PUT' });
    await sleep(8000);
    const ws = await tryTabs();
    if (ws) { log('recovered: replaced the frozen Woolworths tab'); return ws; }
  } catch (e) { log('tab replacement failed:', e.message); }
  if (!canRestart()) throw new Error('the Woolworths tab is frozen and Chrome was restarted recently: try again in a few minutes');
  log('tab still frozen: restarting the server Chrome');
  await restartChrome();
  for (let i = 0; i < 12; i++) {
    await sleep(4000);
    try { const ws = await tryTabs(); if (ws) { log('recovered: server Chrome restarted'); return ws; } } catch { /* Chrome still starting */ }
  }
  throw new Error('the Woolworths tab is frozen and restarting the server Chrome did not bring it back');
}
