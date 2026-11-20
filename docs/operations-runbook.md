# Operations runbook (this fork)

How this install is run day to day. Complements [local-customizations.md](local-customizations.md) (what differs from
upstream) and the private session memory (see "Knowledge base" below). **No personal identifiers here: the fork is public.**

## Session start checklist (Claude Code)

1. Read the **project memory index** (`~/.claude/projects/<this-project>/memory/MEMORY.md`) and the files it lists, at least
   *System map*, *Working rules* and *Open items*. They hold the private facts (agent ids, people, pending work) that must
   not live in git.
2. Read [local-customizations.md](local-customizations.md) before any upgrade or before touching a customized area.
3. `git status` in the live checkout: it must be on `main` and clean. Never develop in it.
4. Confirm the host is healthy: `systemctl --user is-active nanoclaw-v2-*.service`, then `logs/nanoclaw.error.log`.

## Working rules

- **Build in a worktree**, never in the live checkout: `git worktree add ../nanoclaw-wt-<name> -b <branch>`; remove it
  afterwards (`git worktree remove`) and delete the merged branch.
- **PRs target the fork explicitly**: `gh pr create --repo Tangaratta-Engineering/nanoclaw-2.0 ...` (plain `gh` resolves to
  upstream). Subscribe to the PR after creating it.
- **Docs travel with the PR.** Before creating a PR, update `local-customizations.md` / this runbook / the skill docs on the
  same branch, and update the private memory (system file, PR history, open items). After the merge, update memory again
  (PR merged, open item closed). A PR description is not a knowledge base: later sessions will not read it unless told to.
- **Merge only when the owner says "merge #N"** for that PR. Then, in the live checkout:
  `git pull --ff-only origin main` and `pnpm exec tsx scripts/upgrade-state.ts set "" update-nanoclaw`.
- **Before pushing**, `git grep` the diff for personal data (names, member/phone numbers, invoice or channel ids). Use
  made-up examples in tests and docs. Private values go to the database or the private memory.
- Never request or print secrets or one-time codes. Credentials are injected by the gateway; none belong in files under
  `~/projects`, which is mounted read-write into every agent container.
- Anything outward-facing (email, message, insurance claim, publish) needs the owner's explicit approval of that item.
  Approval-gated flows use a code the owner must quote back; a bare "yes" is not approval.
- Tests: `pnpm test` (host), `bun test` in `container/agent-runner`, each skill's own `test_*.py` / `*.test.mjs`.
- Shell notes: `pkill -f`/`pgrep -f` match the invoking shell and kill it, so find the PID with `ps` and `kill` it. `pnpm`
  and `node` are under the nvm directory and are not on PATH in a fresh shell.

## Services on the host

| Unit (user systemd unless noted) | Purpose | Notes |
|---|---|---|
| `nanoclaw-v2-<slug>` | NanoClaw host | restart after host code changes |
| `nanoclaw-voice`, `-voice-timmy`, `-voice-jack` | live Discord voice per agent | restart after merges touching `services/voice` or `speak` |
| `nanoclaw-woolies` + `woolies-chrome` | Woolworths list bridge, Chrome CDP 9222 | sign in via ssh tunnel |
| `nanoclaw-claims` + `claims-chrome` | Peoplecare claims bridge, Chrome CDP 9223 | sign in via ssh tunnel (MFA) |
| `nanoclaw-whatsapp-reader` | read-only WhatsApp store, API 8772 | relink with `pnpm run link` |
| `nanoclaw-pages` | published pages | |
| `audiri.service` (system) | school-app service, 8765 | separate repo |
| host cron | nightly backup, nightly inbox-media purge | `crontab -l` |

Restart a bridge after changing its code: `systemctl --user restart <unit>`. Check `journalctl --user -u <unit> -n 50`.

## The bridge pattern (Woolworths, claims)

Agents cannot reach host programs, so a container skill drops a JSON request into `<queue>/in`, and a host service picks it up,
acts, and writes `<queue>/out`. Browser-driven bridges attach to a dedicated Chrome (xvfb, `--remote-debugging-port`) whose
profile holds the owner's login. Rules:

- The Chrome **profile that holds a login lives outside `~/projects`** (for example `~/.local/share/nanoclaw-<name>/profile`),
  because `~/projects` is visible to every agent container.
- Sign in once with an ssh tunnel: `ssh -L <port>:localhost:<port> <host>`, then `chrome://inspect` on the owner's computer,
  Configure `localhost:<port>`, inspect the page, sign in (MFA included). Sessions survive Chrome restarts.
- Click through the site like a person; deep links often fail. Verify each step landed and fail loudly rather than guess.
- Anything that submits or spends goes behind an approval code, and never retries blindly.

## Troubleshooting by symptom

| Symptom | First checks |
|---|---|
| An agent says a bridge "isn't set up" or gets no answer | unit active? `journalctl --user -u <unit>`; queue folder exists; Chrome unit active; owner still signed in |
| Woolworths bridge says every tab is "frozen" | the bridge now replaces the tab, then restarts `woolies-chrome` itself (log: "recovered"). By hand: `systemctl --user restart woolies-chrome` (profile and sign-in survive); a hung renderer is shared by all tabs, so closing the tab alone does not help |
| Claims bridge says the Peoplecare tab is "frozen" | same as Woolworths: it replaces the tab (on Home), then restarts `claims-chrome` itself (max once per 10 min; log: "recovered"). By hand: `systemctl --user restart claims-chrome`; if that loses the Peoplecare login, sign in again with MFA. A claim part-way through is lost on a restart (submit then says to prepare again) |
| Voice call never answers until George mutes, or says "I didn't get that" a lot | background noise keeping the clip open: look for `clip:` and `background noise ignored` lines (`journalctl --user -u nanoclaw-voice`); tune `VOICE_VOICE_RMS` / `VOICE_FLOOR_MULT` in the unit's env file; `VOICE_NOISE_GATE=0` turns the audio-level endpointing off |
| Bridge says NOT signed in | sign in again through the ssh tunnel; do not retry in a loop |
| Agent cannot reach a container service by name | container proxy: only `.home` bypasses the gateway; call with `trust_env=False` or use a `.home` name |
| Scheduled task rejected as too frequent | write a gate `--script` that returns `{"wakeAgent": bool, "data": ...}` instead of overriding the limit |
| A push or command is blocked by the auto-mode classifier | run single plain commands; scrub personal data; do not work around a block, ask the owner |
| `gh pr create` says "No commits between" | wrong repo: add `--repo Tangaratta-Engineering/nanoclaw-2.0` |

## Knowledge base

Two parts, both loaded at session start (see the checklist):

1. **This public runbook and `local-customizations.md`** in git: how the install works and how to upgrade it.
2. **The private project memory** (`~/.claude/projects/<this-project>/memory/`, index `MEMORY.md`): agent ids, people, the
   state of each system, standing rules and open items. Not in git.

Keep both current: when a system changes, update its memory file in the same session; add a row to
`local-customizations.md` for every new customization; and before ending a session refresh *Open items* (remove what is done,
add what is pending and who it is waiting on).
