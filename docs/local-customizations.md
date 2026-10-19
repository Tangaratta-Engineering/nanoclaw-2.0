# Local customizations (this fork)

This fork (`Tangaratta-Engineering/nanoclaw-2.0`) runs NanoClaw with changes that are **not** upstream.
Read this before running `/update-nanoclaw` or `/update-skills`, and update it whenever a customization is
added, moved or dropped. Keep personal identifiers (user, server, channel, bot ids) out of this file —
the fork is public.

## How upgrades work here

- Upgrades go through `/update-nanoclaw` (merge-based, with a backup branch + tag and a dry-run conflict
  preview). A scheduled check (`nanoclaw-update-check.service`) prepares upgrade worktrees under
  `~/projects/.nanoclaw-updates/<install>/<timestamp>-<from>-<to>/` on branches named
  `update-nanoclaw/<timestamp>-<from>-<to>`.
- A prepared upgrade branch is based on the commit that was current **when it was prepared**. If more
  customizations land afterwards (as happened with the Discord/agent work below), either re-run the
  update on the new `main`, or merge the prepared branch and resolve the conflicts listed here.
- Channel adapters (`src/channels/discord.ts`, `telegram.ts`, …) are installed from the `channels`
  branch by `/add-<channel>` skills and re-copied by `/update-skills`. **Never edit them in place** — put
  customizations in a separate file and import it from the `src/channels/index.ts` barrel.

## Customizations

| # | What | Files | On upgrade |
|---|------|-------|-----------|
| 1 | Second Discord bot (own identity/DM) as adapter instance `timmy`, plus role-mention support for both Discord bots | `src/channels/discord-timmy.ts`, `src/channels/discord-timmy-registration.test.ts`, one import line in `src/channels/index.ts` | Merges cleanly (isolated on purpose). After upgrade confirm `pnpm test` (registration test) and the startup log line `Channel adapter started … channel="discord-timmy"`. Depends on `createChatSdkBridge({ instance })` and the Discord adapter option `mentionRoleIds`. |
| 2 | HTTP/SSE MCP servers in the container config (`ncl groups config add-mcp-server --url …`) | `src/container-config.ts`, `src/cli/resources/groups.ts`, `container/agent-runner/src/{config.ts,index.ts,providers/types.ts}` | **Superseded by upstream** (`McpHttpServerConfig` and a native `--url` flag). On conflict take upstream's side for all five files, then verify existing entries still load: `ncl groups config get --id <group>` and a test message that uses the tool. |
| 3 | Destinations named `*-main` post at channel level (not inside the session's thread) | `container/agent-runner/src/poll-loop.ts` (`sendToDestination`), `container/agent-runner/src/mcp-tools/core.ts` (`resolveRouting`) | Will conflict (upstream reworked both). Re-apply the intent: when the destination name ends in `-main`, force `thread_id = null` (and `in_reply_to = null`). Candidate to propose upstream. |
| 4 | **Fix** — Discord button clicks mis-decoded (`ncq:<id>:<idx>\n<value>` read as `"0\n0"`): approvals looked rejected, cards showed `0`. Bug in the bridge vs `@chat-adapter/discord` 4.29.0's newline-delimited `custom_id`; still present in upstream `main` | `src/channels/chat-sdk-bridge.ts` (`parseDiscordCustomId`, raw interaction handler), `src/channels/chat-sdk-bridge.test.ts` | Will conflict if upstream rewrites that handler. Keep upstream's version only if it strips the `\n<value>` suffix (the tests here fail otherwise); else re-apply `parseDiscordCustomId`. Candidate to send upstream. |
| 5 | Shared agent base prompt no longer contains a persona line | `container/CLAUDE.md` | Re-apply: persona belongs in each group's own `CLAUDE.local.md`, not in the base prompt every agent inherits. |
| 6 | `pnpm run chat --to <channelType>:<platformId>` admin injection; Remote Control (phone admin session) unit and docs | `scripts/chat.ts`, `systemd/claude-rc.service`, `CLAUDE.md` (Remote Control section) | `CLAUDE.md` will conflict textually — keep both sides. |
| 7 | **Default agent for un-addressed channel messages**: a message with no @handle, at channel level (not in a thread), from a non-bot, in a wired chat, (text **or an attachment** — a Discord voice message has no text) is re-injected as a mention of the default bot so its agent handles it (then delegates per its rules) | `src/channels/default-agent.ts`, `src/channels/default-agent.test.ts`, one import line in `src/channels/index.ts` | Merges cleanly (isolated). Relies on `registerMessageInterceptor` + `routeInbound` in `src/router.ts` and the wiring being `mention-sticky`; the tests guard the loop/thread/other-bot exclusions. After upgrade check those two router exports still exist. |
| 8 | **`transcribe` container skill** — speech-to-text for voice messages and audio files with a **reliability rating**. Primary engine: Groq `whisper-large-v3` via the OneCLI vault (key never visible to agents), always cross-checked against `whisper-large-v3-turbo` (disagreement ⇒ `uncertain`); automatic offline fallback to local faster-whisper `small`. Agents get an always-on `instructions.md` fragment that tells them to report uncertainty and not act on shaky transcripts | `container/skills/transcribe/` (new files only: `SKILL.md`, `instructions.md`, `vocabulary.txt`, `scripts/`, `setup.sh`, `requirements.lock`) | Merges cleanly (new directory); conflicts only if upstream ships its own skill with this name. Needs the **Groq secret in the OneCLI vault** (generic, host `api.groq.com`, header `Authorization`, format `Bearer {value}`) — vault state is not in git. The local fallback's packages/models live outside the repo and image; if an upgrade changes the image's Python version or architecture, re-run `container/skills/transcribe/setup.sh`. Depends on the `/workspace/projects` mount and `curl`/`ffmpeg`/`python3`+`pip3` in the image. |
| 9 | **`speak` container skill** — agents reply with a spoken voice message. Local Piper TTS (free, offline, ~4× real time on this CPU); per-agent voice in `voices.json` (Tiff / Timmy); text is cleaned for speech (no links, markdown, emoji; `$1,789` → "1,789 dollars"); output is Opus-in-Ogg 48 kHz mono encoded with PyAV so **no system ffmpeg is needed**; attached with the existing `send_file` tool. An always-on `instructions.md` tells agents to reply in voice when George sends a voice note, keep it short, and put links/details in a normal text message | `container/skills/speak/` (new files only: `SKILL.md`, `instructions.md`, `voices.json`, `scripts/`, `setup.sh`, `requirements.lock`) | Merges cleanly (new directory). Packages and voices live outside the repo and image (`~/projects/.nanoclaw-tools/piper`); re-run `container/skills/speak/setup.sh` if an upgrade changes the image's Python version or architecture. Piper has no Australian voices; an Australian engine (e.g. Google Cloud TTS) would be an extra, with Piper as fallback. |

### Older customizations (predate the above)

`CONTAINER_DNS` override (`src/config.ts`, `src/container-runner.ts`); a read-write mount of the projects
directory at `/workspace/projects` (`src/container-runner.ts`); the dashboard pusher
(`src/dashboard-pusher.ts`, `src/index.ts`); the Telegram adapter and its helpers (legacy, unused);
Python/nutrition dependencies in `container/Dockerfile`; an editor workspace file. A prepared upgrade
branch already ports these to the new DB API — prefer its resolutions.

## State that is NOT in git (survives upgrades; back it up)

- `.env` — bot tokens and ids for both Discord bots (`DISCORD_*`, `DISCORD_TIMMY_*`, `*_MENTION_ROLE_IDS`),
  OneCLI settings. Never commit.
- `data/v2.db` — agent groups, messaging groups, wirings (the #general wirings are `mention-sticky`; keep it that way — the default-agent rule depends on it), destinations (including agent-to-agent and the
  `*-main` channel-level destinations), members, roles, container configs (model, effort, MCP servers).
- `groups/<folder>/` (gitignored) — each agent's `CLAUDE.local.md` (persona, the delegation/handoff protocol between the two agents with its criteria and hop limit, visibility rules; handoff context includes the audio transcript since files are not forwarded; the "hand to the other agent" triggers cover natural wording such as "I think you need Timmy for that", so you never have to @-tag), skills, and `.claude/agents/*` (for example a model-pinned flight-planner subagent).
- Agent memory: `data/v2-sessions/<agent-group>/.claude-shared/projects/-workspace-agent/memory`. One
  agent's memory directory is a **symlink** into another's via the `/workspace/projects` mount, so it only
  resolves inside a container. If an upgrade changes or removes that mount, re-create the link or copy.
- `~/projects/.nanoclaw-tools/whisper/` — packages (`site/`) and local Whisper models (`models/`) for the `transcribe` skill's offline fallback; rebuild with `container/skills/transcribe/setup.sh` (about 0.5 GB for `small`, plus `medium` if you add it).
- `~/projects/.nanoclaw-tools/piper/` — Piper packages (`site/`) and voices (`voices/`, about 60 MB each) for the `speak` skill; rebuild with `container/skills/speak/setup.sh`.
- OneCLI vault secret `Groq` (the transcription API key). To restore: create a generic secret, host `api.groq.com`, header `Authorization`, format `Bearer {value}`; verify with `onecli run --agent <id> -- curl -s https://api.groq.com/openai/v1/models`.
- OneCLI vault (agents, secrets) and `~/.config/nanoclaw/mount-allowlist.json`.

Agent identifiers must satisfy OneCLI: 1–50 chars, start with a **letter**, lowercase letters, digits and
hyphens. Groups created with `ncl groups create` get a UUID id that often starts with a digit and is
rejected (`400` on container start). Create groups with an `ag-<timestamp>-<suffix>` id instead.

## Testing container skills

Agents do **not** run `nanoclaw-agent:latest`. They run the per-install image `nanoclaw-agent-v2-<slug>:latest` (and per-group images built on it, `…:<agent-group-id>`), which can be older and lacks tools the base image has — notably **`ffmpeg`/`ffprobe`**. Test a skill in the image agents actually use (`docker images | grep nanoclaw-agent-v2-`), with `--network none` when it is meant to work offline, and do not depend on system packages that image does not have (bundled libraries such as PyAV are fine).

## Upgrade checklist

1. Let agents go idle (no processing messages) — restarts kill running containers.
2. Backup: `/update-nanoclaw` creates `backup/pre-update-*`; also copy `.env`, `data/v2.db`, `groups/`.
3. Dry-run first: `git merge --no-commit --no-ff upstream/main` in a throwaway worktree; compare the
   conflicts with the table above. Anything new means a customization needs a new row here.
4. Resolve per the "On upgrade" column. Then `pnpm install --frozen-lockfile`, `pnpm run build`,
   `pnpm test`, `pnpm exec tsc -p container/agent-runner/tsconfig.json --noEmit`.
5. `./container/build.sh` if the container image or agent-runner dependencies changed.
6. Restart (`systemctl --user restart nanoclaw`) and verify: both Discord adapters start; an agent answers
   in its DM and, when @mentioned, in the server channel; agent-to-agent messaging still works.
7. Update this file.
