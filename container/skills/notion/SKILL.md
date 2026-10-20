---
name: notion
description: Search, read, create and update Notion pages (as Markdown) for George. Use when he asks to look something up in Notion, save notes/plans/itineraries to a Notion page, or edit an existing one.
allowed-tools: Bash(/app/skills/notion/scripts/notion:*)
---

# Notion

```bash
N=/app/skills/notion/scripts/notion
$N search "rotorua itinerary"            # title | id | url | last edited
$N get <page-url-or-id>                  # page content as Markdown
$N create --parent <page> --title "Rotorua trip" --file /tmp/body.md   # or pipe Markdown on stdin
$N append <page> --file /tmp/more.md     # add to the end
$N edit <page> --old "TBC" --new "Booked" [--all]   # targeted change
$N replace <page> --file /tmp/new.md --yes-overwrite  # whole-page rewrite
```

Pages can be given as a Notion URL, a 32-character id or a dashed UUID. `search` only finds pages shared with the integration.

## Notes

- The integration token lives in the OneCLI vault (host `api.notion.com`); you never see it. If you get a 401/403, tell George the Notion integration needs attention — do not ask for a token.
- A 404 usually means the page is not shared with the integration: George must open the page → ••• → Connections → add it.
- `create` needs a parent **page** (not a database). If George has not said where, search for a sensible parent or ask once.
- Pages are read and written as Markdown; Notion-specific blocks may appear as tags (`<callout>`, `<unknown>`). Databases/rows are not supported by this tool.
