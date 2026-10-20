---
name: handover
description: Get or give working context between Tiff and Timmy instead of making George repeat himself. Use when George refers to something the other agent was doing, or when the other agent asks you for a handover.
allowed-tools: Bash(/app/skills/handover/scripts/recent-context:*)
---

# Handover between agents

The protocol (CONTEXT REQUEST → HANDOVER) is in the always-on instructions; this page covers the tool.

## `recent-context`

```bash
/app/skills/handover/scripts/recent-context [--hours 24] [--max-chars 9000] [--grep WORD ...]
```

Prints a compact timeline of your own recent conversations, newest first — George's messages (and where they came from), what you replied, the tool calls you ran and, prominently, any **errors** (`! ERROR …`). `ME` marks what you said. Use `--grep` with topic keywords to focus on one task, `--hours 72` to look further back, and `--max-chars` to keep the pack short. It reads only your own conversation records.

## Writing a good HANDOVER

Facts, not a transcript: what George originally wanted, what was done, what failed (quote the exact error), the state (ids, file paths, links, drafts, anything created or sent), his stated preferences, open questions, a suggested next step. Under ~300 words. Say "I don't have this" for gaps rather than guessing.

## Why

George often asks Timmy when Tiff is struggling (and the other way round). The agent taking over should ask its sibling for the context, not ask George to explain it all again.
