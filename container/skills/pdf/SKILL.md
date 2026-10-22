---
name: pdf
description: Read the text of a PDF — an attachment George sent, a file in the workspace, a PDF link, or a PDF attached to an email. Use for invoices, statements, forms, tickets, brochures, reports.
allowed-tools: Bash(/app/skills/pdf/scripts/pdf-text:*)
---

# PDF text

```bash
P=/app/skills/pdf/scripts/pdf-text
$P /workspace/inbox/<id>/invoice.pdf                 # a file George sent in chat
$P https://example.com/brochure.pdf --pages 1-3      # a PDF link
$P --gmail <message id> --name invoice               # a PDF attached to an email (message id from the inbox dataset)
$P statement.pdf --layout                            # keep columns: better for tables and invoices
```

Prints `--- page N of M ---` followed by the page text. Options: `--pages 1-3,5`, `--layout`, `--max-chars 20000` (default; read the rest with `--pages`).

## What it cannot do

- **Scanned or image-only PDFs** have no text layer: the tool says so (`NO TEXT LAYER`). Then open the PDF with the Read tool, which can view pages as images, or ask George for a text version. There is no OCR here.
- **Password-protected PDFs** are reported, not opened.
- A URL that returns a web page instead of a PDF is rejected: use WebFetch for pages.

## Setup (host, once)

`NANOCLAW_AGENT_IMAGE=<agent image> container/skills/pdf/setup.sh` installs pinned `pypdf` into `~/projects/.nanoclaw-tools/pdf` (shared with `inbox-triage`).
