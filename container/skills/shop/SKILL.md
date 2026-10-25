---
name: shop
description: Build a pre-filled cart link for one of George's regular online shops (Shopify stores), so he only has to open it, check it and pay. Use when he says to reorder, restock, "put my usual in the cart", or asks to buy tissues, toilet paper, kitchen paper, coffee or other regular items from a set-up shop.
allowed-tools: Bash(/app/skills/shop/scripts/shop:*)
---

# Regular online orders → a ready-to-pay cart link

```bash
S=/app/skills/shop/scripts/shop
$S cart whogivesacrap tissues=3 kitchen_paper=2     # named items and quantities
$S cart whogivesacrap tissues toilet_paper          # a bare name uses its usual quantity
$S cart whogivesacrap --usual                       # every item marked in_usual_order, at its usual quantity
$S catalog whogivesacrap                            # what the store sells now: handle | variant | price | stock
```

**Send the result as a card with a tappable button, not as text.** Add `--card` and pass the printed JSON straight to the `send_card` tool (its `card` and `fallbackText` fields, unchanged):

```bash
$S cart whogivesacrap tissues=2 kitchen_paper=2 --card     # prints {"card": {...with a link button...}, "fallbackText": "..."}
```

A bare cart URL contains `:` and `,`, which chat apps often fail to link; the button always works. In a live voice call, say you have sent the cart to Discord instead of reading the link.

The output lists each line with the live price, the subtotal, a **store check** (the tool opens the link, reads the store's own cart back and confirms it holds exactly those items), any price changes since the last order, and the link. Send George all of it. He opens the link, lands on the store's checkout page with the cart filled, checks it and pays.

## Rules

- **You never buy anything.** No logins, no checkout, no payment details, no passwords. The tool only does read requests to the store's public pages and its cart link.
- **No substitutions.** If an item is out of stock, renamed or ambiguous the tool refuses; tell George and let him choose. Never swap in a different size, flavour or brand.
- **Ask which items** unless he named them or said "my usual". His orders are not always the same mix; the shop's `notes` in its config say what is typical. If you use "usual", say exactly which items and quantities you included.
- Quote the subtotal as "before shipping, discounts and GST": those only appear at checkout. If the tool reports a price change, say so.
- Do not send the link if the tool printed an error instead of "Store check".

## Setting up a shop (once per store)

Create `<data dir>/<name>.json` (default data dir `/workspace/projects/.nanoclaw-data/shopping/`, outside git, since it describes personal buying habits; see `shop.example.json`). It fixes the store's domain — the tool talks to no other host — and lists nicknames:

```json
{"store": "shop.example.com", "label": "Example Shop", "notes": "typical order…",
 "items": {"tissues": {"handle": "product-handle", "variant": "12 Boxes", "usual_qty": 3, "last_price": 27.0, "in_usual_order": true}}}
```

`handle` is the product's URL name; `variant` is a fragment of the variant title (omit when the product has one). Find handles with `shop catalog`. Work out the usual items and quantities from the shop's order confirmation emails (`inbox-mail search`). Only Shopify stores work this way (`/products.json` and `/cart/<variant id>:<qty>` links); other platforms need their own method.

Tests: `python3 container/skills/shop/scripts/test_shop.py`.
