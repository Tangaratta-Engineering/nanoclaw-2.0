---
name: story-map
description: Manage George's Life Story Map, his visual card wall of every project and task at home and with the family. Use when George asks to add, change, tick off, move or remove anything on "the board", "the wall", "the story map" or "the roadmap", gives you a project or task to track, or asks what's on it or what's still open.
allowed-tools: Bash(/app/skills/story-map/scripts/storymap:*)
---

# Life Story Map

George plans home and family life on a wall of coloured index cards, adapted from software user story mapping. The digital version is a live web page: **https://roadmapping.netlify.app**

You keep that board up to date. George tells you what changed in plain words; you turn that into precise edits with `storymap.py`. Each edit is saved to GitHub, and the web page updates within about a minute.

## How the board works

Read the board left to right by theme, top to bottom by detail.

| Card | Colour | What it is | How to write it |
|---|---|---|---|
| Category | Green | A broad theme across the top | Short noun phrase: "Family Activities", "George's Projects" |
| Outcome | Blue | An event or core outcome under a category; starts a column | The thing to achieve or the event: "Mum's birthday", "Gates / front porch" |
| Result | Yellow | A result that proves the outcome is done; stacks under its outcome | **Describe the finished state, not the action.** "Locks fitted", not "Fit locks". "Packing list done", not "Write packing list" |
| Unknown | Pink | A research item or open question; something that can't just be done yet because it needs finding out first | A question or the thing to find out: "Xmas where?", "Are we making the chestplate from EVA foam, or buying it?" |

Other conventions already on the wall:

- **(H)** and **(S)** at the end of a card mean it's for Henry or Sophie. A "Henry:" prefix means the same.
- A **sub-heading** is a green column inside a category (for example "Outside" under George's Projects). Its cards can be blue outcome cards. Use one only when George asks for a sub-group.
- A ticked **result** means achieved. A ticked **unknown** means answered. Ticked cards stay on the board, shown crossed out.
- Card text can span lines (use `\n`). Keep it short; these are index cards (280-character limit).

### Coaching George on wording

When George asks for a yellow card worded as a task ("buy fireworks tickets"), save it as a result ("Fireworks tickets bought") and tell him in one line what you changed. If the card is really something he doesn't know yet ("figure out where we're going"), make it pink instead. If something is too big to be one card ("Organise Xmas"), suggest it's an outcome (blue) with cards under it, and ask before creating several cards.

## Setup (done once by the host)

`storymap` is at `/app/skills/story-map/scripts/storymap`. There is no token in the container: the OneCLI gateway injects George's GitHub credential for `api.github.com` (a fine-grained token limited to the **firsthalfhero/roadmapping** repo, Contents: read and write). Check reading works with `storymap show`. If a command fails with HTTP 401, 403 or 404, the credential is missing or expired: tell George, don't ask him for a token in chat.

Optional environment variables: `STORYMAP_REPO` (default `firsthalfhero/roadmapping`), `STORYMAP_BRANCH` (default `main`).

## Commands

Run every command as `/app/skills/story-map/scripts/storymap <command> ...` (written `storymap` below). Ids look like `g1`, `o12`, `c3f9a1b`; get them from `show` or `find`.

**Reading**

| Command | What it does |
|---|---|
| `show` | Prints the whole board, with ids and done/open state |
| `show --open-only` | Hides ticked cards; use this for "what's left?" |
| `show --json` | Raw data |
| `find "text"` | Case-insensitive search across categories, outcomes and cards |
| `validate` | Checks the saved map is well-formed |

**Changing** (each one is a single commit)

| Command | What it does |
|---|---|
| `add-category "Title" [--index N]` | New green category (default: far right) |
| `add-outcome CATEGORY_ID "Title" [--index N] [--subheading]` | New blue column under a category |
| `add-card OUTCOME_ID result "Text" [--index N] [--done]` | New yellow card (default: bottom of the column) |
| `add-card OUTCOME_ID unknown "Text"` | New pink card |
| `edit ID "New text" [--type result\|unknown]` | Reword any card, outcome or category |
| `retype ID result\|unknown` | Switch a card between yellow and pink |
| `done ID [ID ...]` | Tick off one or more cards |
| `undo ID [ID ...]` | Reopen ticked cards |
| `move CARD_ID --to OUTCOME_ID [--index N]` | Move a card to another column |
| `move OUTCOME_ID --to CATEGORY_ID [--index N]` | Move a whole column to another category |
| `move ID --index N` | Reorder within its current place (works for categories too) |
| `remove ID` | Delete a card, or an empty outcome or category |
| `remove ID --force` | Delete an outcome or category **and everything under it** |
| `import FILE` | Replace the whole board with JSON George copied from the page |

Global options go **before** the command: `--dry-run` (show what would change, save nothing), `-m "message"` (custom commit message), `--file map.json` (edit a local file instead of GitHub, for testing).

`--index` is 0-based: `--index 0` puts it first or at the top.

## How to handle a request

1. **Look before you change.** Run `find` (or `show`) to get the real ids. Never guess an id.
2. **If the match is ambiguous, ask.** For example, there are two "Packing list" cards (Blue Mountains and Umina).
3. **Make the change** with the narrowest command. To change several cards, run several commands; each is its own commit.
4. **Confirm back in one or two lines** with what changed and where, e.g. "Added 'Fireworks tickets bought' under Xmas + New Year." Mention that the board updates in about a minute only if George seems to be watching it.

### Ask George before you:

- `remove` anything with `--force` (deletes a whole column or category)
- `import` (replaces the whole board)
- delete a card he might want ticked instead. Default to `done`, because finished cards are a record of progress. Remove only when he says it's no longer relevant, was added by mistake, or is a duplicate.
- restructure: create several cards at once, merge columns, or rename a category

### Examples

| George says | You run |
|---|---|
| "Add getting the trailer registered to the Umina trip" | `find Umina` → `add-card <umina-id> result "Trailer registration current"` |
| "We've booked the Blue Mountains place" | `find "Blue Mountains"` → `add-card <id> result "Accommodation booked" --done` (or tick an existing card) |
| "Locks are on the gate" | `find locks` → `done <id>` |
| "Not sure if we're doing Xmas at home or Rob's, put that on" | `find Xmas` → check whether "Xmas where?" already covers it; if so, tell him it's there |
| "Christmas is at home, sorted" | `find "Xmas where"` → `done <id>`, and optionally `edit <id> "Xmas where?\nAt home"` |
| "Move the roof rack question to the summer holiday" | `find "roof rack"` and `find "Summer"` → `move <card-id> --to <summer-id>` |
| "New category for the school P&C" | `add-category "School P&C"`, then ask what outcomes go under it |
| "What's left for Halloween?" | `find Halloween` → `show --open-only`, and summarise that column only |
| "Halloween's done, clear it off" | Ask whether to tick the remaining cards or remove the column, then act |

## When George edits on the page

George can drag cards around and edit them on the web page, but **the page can't save**. His changes disappear on refresh. When he wants them kept, he taps **Copy / load map → Copy** and pastes the JSON to you. Then:

1. Save the pasted JSON to a temporary file.
2. Compare it with the current board (`show`). If the board was updated after he copied, his paste would undo those changes. Tell him what would be lost and ask before going ahead.
3. `storymap import /path/to/file.json` (try `--dry-run import ...` first to validate).

## Things not to do

- Don't edit `index.html`, `netlify.toml` or anything except `map.json`, and only through `storymap.py`. The page's code and features are maintained separately.
- Don't commit to any branch other than `main`.
- Don't put anything sensitive on cards (health details, money, addresses, passwords). The site is **public to anyone with the address**.

## Troubleshooting

| Problem | Fix |
|---|---|
| HTTP 401 / 403 | The vault credential expired or lacks Contents: Read and write on the roadmapping repo. Tell George; he renews it in OneCLI. |
| HTTP 404 | Wrong repo name, or the credential can't see the repo. |
| `map.json changed ... retrying` | Handled automatically (someone else saved at the same time). If it fails three times, run the command again. |
| `Change would make the board invalid` | Nothing was saved. Read the message; usually an empty title or a card in the wrong kind of column. |
| Board on the website hasn't changed | Netlify takes about a minute after each commit. Then refresh the page. The "Board last saved" line at the top shows the time of the latest save. |

## Data format (reference)

`map.json` in the repo root. The tool maintains it; this is for reading `show --json` output.

```json
{
  "version": 1,
  "updated": "2026-11-03T09:15:00+00:00",
  "groups": [
    { "id": "g1", "title": "Weekends / Holidays / Trips",
      "outcomes": [
        { "id": "o2", "title": "Blue Mountains trip",
          "items": [
            { "id": "i3", "type": "pink",   "text": "Nala feed + care", "done": false },
            { "id": "i5", "type": "yellow", "text": "Julie plan / task list", "done": false }
          ] },
        { "id": "o53", "title": "Outside", "kind": "green",
          "items": [ { "id": "i54", "type": "blue", "text": "Driveway pebbles", "done": false } ] }
      ] }
  ]
}
```

- `groups` = green categories, left to right. `outcomes` = columns, left to right. `items` = cards, top to bottom.
- `type`: `yellow` result, `pink` unknown, `blue` outcome card (only inside a `"kind": "green"` sub-heading column).
- Ids are unique strings. Never reuse one.
