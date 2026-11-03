---
name: woolworths
description: Put groceries on George's Woolworths shopping list so he can check out later from the app or website. Use when he asks to add something to his Woolworths or shopping list ("add milk to Woolies"), asks what is on it, or what he usually buys there.
allowed-tools: Bash(/app/skills/woolworths/scripts/woolies:*)
---

# Woolworths list

George shops online at woolworths.com.au. You add items to a **list** in his account (the list called `NanoClaw`); the list shows in his app and on the website, so when he is ready he opens it, adds the items to his trolley and checks out himself. You never touch the trolley, checkout or payment.

```bash
W=/app/skills/woolworths/scripts/woolies
$W status                          # is the server's Woolworths login working?
$W usual "milk"                    # what George has bought before (his usual brand and size): try this FIRST
$W search "parmesan block"         # all Woolworths products
$W add 88436 6023717=2             # ADD to the NanoClaw list: STOCKCODE (1) or STOCKCODE=QTY
$W set 6023717=4                   # make the list hold exactly 4 of that product
$W show                            # what is on the NanoClaw list
$W lists                           # all his Woolworths lists
$W add --list "Party" 12345        # another list (it must already exist)
```

Items print as `stockcode | name | size | price | cup price | notes`. The stockcode is what you pass to `add`.

## How to handle "add X"

1. `usual "X"` first. If one product clearly matches what he asked for (right type, and the size if he gave one), add it and say what you added, with size and price.
2. If several of his usual products match, or he gave no size and the sizes differ a lot, show the top two or three (name, size, price) and ask which. If nothing matches in his history, use `search` and ask before adding the first hit.
3. Never guess brands or sizes, never substitute silently, and tell him about anything marked UNAVAILABLE.
4. After `add`, confirm in one line: what went on the list and the running total of items (`show` if useful). Remind him the list is called NanoClaw in his Woolworths app only if he seems unsure.
5. **Quantities: always pass the number George says.** "2 milk", "a dozen" (12), "half a dozen" (6), "a couple" (2) become `STOCKCODE=2` and so on; only a bare item with no number means 1. `add` ADDS to what is already on the list, so never run it again to "fix" a quantity: use `set STOCKCODE=N` (exact quantity; it can lower it too). Both print what the list really holds afterwards (`x3 ...`); check that line against what George asked for, and tell him if it is not confirmed.

## Rules and limits

- The bridge works through George's own signed-in browser on the server. If a command says NOT signed in or the bridge doesn't answer, tell George plainly (he signs in again with the ssh tunnel); don't retry in a loop.
- Be gentle with the site: batch several items into one `add`, and don't run dozens of searches in a row.
- `show` can lag a few seconds behind `add` (Woolworths updates its list view slowly), so don't treat a just-added item as missing; adding the same product again keeps one row and raises its quantity.
- There is no remove or clear command. If he wants an item removed, tell him to delete it in the app.
- Prices and availability are live from the site and can change before he checks out.
