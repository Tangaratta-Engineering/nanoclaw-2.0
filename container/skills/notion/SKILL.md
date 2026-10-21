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
$N move <page> --to <new-parent-page>      # re-parent a page (never to the top level: the API cannot)
$N replace <page> --file /tmp/new.md --yes-overwrite  # whole-page rewrite
```

### Databases (real tables with columns)

```bash
$N db-create --parent <page> --title "Packing list" \
   --columns "Item:title,Person:select(George|Emily|Henry|Sophie),Packed:checkbox,Qty:number,Due:date,Tags:multi(camp|beach),Notes:text"
$N db-schema <database>                          # column names, types, select options
$N db-add-row <database> --set Item=Passport --set Person=George --set Packed=no
$N db-add-rows <database> --file rows.json       # JSON array of {"Column": "value"}; use for many rows
$N db-query <database> --where Packed=false --where "Person=Emily" --sort Due:asc
$N db-update-row <row-id> --set Packed=yes
$N db-alter <database> --add "Notes:text" --rename "Qty=Count"   # --remove Col needs --yes-remove
```

Column types: `title` (exactly one; added as "Name" if you omit it), `text`, `number`, `select(a|b)`, `multi(a|b)`, `date`, `checkbox`, `url`, `status`. Values: checkbox `yes/no`, multi-select `a|b`, date `2026-10-30` or `2026-10-30/2026-11-02`, empty or `null` clears a cell. Filters: `Col=value`, `Col~text` (contains), `Col<date`, `Col>date`. Run `db-schema` first if unsure of the column names. Rows are pages: `get`/`append` work on a row id for its body.

Pages can be given as a Notion URL, a 32-character id or a dashed UUID. `search` only finds pages shared with the integration.

## Notes

- The integration token lives in the OneCLI vault (host `api.notion.com`); you never see it. If you get a 401/403, tell George the Notion integration needs attention — do not ask for a token.
- A 404 usually means the page is not shared with the integration: George must open the page → ••• → Connections → add it.
- `create` needs a parent **page** (not a database). If George has not said where, search for a sensible parent or ask once.
- Pages are read and written as Markdown; Notion-specific blocks may appear as tags (`<callout>`, `<unknown>`). Database rows are read and edited with the `db-*` commands (a row's own body with `get`/`append`).
