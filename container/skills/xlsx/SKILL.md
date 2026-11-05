---
name: xlsx
description: Create, read, edit and check Excel spreadsheets (.xlsx). Use whenever George wants a spreadsheet, budget, tracker, list, table or report as an Excel file, or sends you an .xlsx or .csv to read, clean up or add to.
allowed-tools: Bash(/app/skills/xlsx/scripts/xlsx:*)
---

# Excel spreadsheets

```bash
X=/app/skills/xlsx/scripts/xlsx
$X build spec.json /workspace/agent/budget.xlsx    # new workbook from a JSON spec
$X build data.csv  /workspace/agent/data.xlsx      # CSV -> formatted workbook
$X inspect file.xlsx --rows 40                     # read what is in a workbook (formulas as written)
$X check file.xlsx                                 # lint formulas and values (exit 1 if problems)
```

Then send it with `send_file` (the `path`, and `to` set to the chat you are replying in). Say what is in it in a sentence or two; do not paste the whole table into chat.

## Spec

```json
{"font": "Arial",
 "sheets": [{
   "name": "Budget",
   "columns": [{"header": "Item", "width": 28},
               {"header": "Cost", "format": "$#,##0.00"},
               {"header": "Due", "type": "date"}],
   "rows": [["Rent", 1200, "2026-11-01"], ["Power", 180.5, "2026-11-15"]],
   "totals": {"label": "Total", "columns": ["B"]},
   "notes": ["Source: amounts from George, 6 Nov 2026"]}]}
```

- A cell that is a string starting with `=` is a formula (`"=B2*1.1"`). `totals` adds a bold `SUM` row.
- `type: "date"` takes `YYYY-MM-DD` and stores a real date. `format` is any Excel number format (`0.0%`, `$#,##0`, `0.00`). Percentages are stored as fractions (0.15 shows 15%).
- Header row, freeze panes, filter buttons and column widths are done for you. Defaults: Arial, dark header.

## Rules

- **Use formulas, not typed results.** Totals, differences and percentages must be formulas so the sheet recalculates when George changes an input.
- **Put assumptions in the sheet.** Rates, growth, hours: one labelled cell each, referenced by formulas, and a `notes` line saying where each number came from (George said it, or the source). Never invent a figure; leave it blank and say so.
- **Follow the request literally**: exact tab names, exact column headers, the formula he spelled out.
- Sheet names with spaces must be quoted in formulas: `='Q1 Sales'!B2`. Use Excel-2007-era functions (`SUMIFS`, `INDEX`/`MATCH`, `IFERROR`, `SUMPRODUCT`). Avoid `XLOOKUP`, `FILTER`, `SORT`, `UNIQUE`, `SEQUENCE`: sort and filter in Python before writing. `TEXTJOIN`, `CONCAT`, `IFS`, `SWITCH`, `MAXIFS`, `MINIFS` need the `_xlfn.` prefix.
- **Always run `check`** before sending and fix anything under `problems`. A clean check means no obvious breakage, not that the numbers are right: spot-check two or three formulas against a figure you can work out by hand.
- **Editing George's own workbook**: copy it first (never overwrite the original), match its fonts, colours and layout, write only into the cells meant for input, and leave existing formulas alone. With openpyxl, open with `load_workbook(path)` (not `data_only=True`, which would turn every formula into a fixed number when saved) and add `keep_vba=True` for `.xlsm`.
- A workbook for someone to fill in needs a short legend saying which cells to edit and one example row.
- Money and personal records are private: save under `/workspace/agent/`, never publish a spreadsheet with the `publish` skill.

## Limits

- No LibreOffice here, so formulas have **no stored results** until the file is opened in Excel, Google Sheets or a phone app. Chat and email previews may show formula cells blank. Tell George that once when you send a file with formulas; if he needs the numbers visible in a preview, also state the key results in your message.
- `check` cannot compute formulas; it only finds structural problems.
- For anything beyond the spec (charts, conditional formatting, data validation, multiple styles) write a short Python script with `openpyxl` and then run `check`:
  `import sys; sys.path.insert(0, "/workspace/projects/.nanoclaw-tools/xlsx/site"); import openpyxl`
- 500,000 cells maximum per build.

## Setup (host, once)

`NANOCLAW_AGENT_IMAGE=<agent image> container/skills/xlsx/setup.sh` installs pinned `openpyxl` into `~/projects/.nanoclaw-tools/xlsx`. If `xlsx` says openpyxl is missing, reply in text and tell George to run it.
