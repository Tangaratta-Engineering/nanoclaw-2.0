# Nutrition Tracker CLI Documentation

The `nutri_cli.py` script provides a command-line interface to the Nutrition Tracker API. All output is JSON to stdout; errors go to stderr.

**Exit codes:**
- `0` — success
- `1` — unexpected error (e.g., network timeout)
- `2` — missing prerequisite (e.g., food not found when saving recipe, unknown person)
- `3` — AI failure (vision OCR returned invalid JSON, or a `log` item failed on the AI estimate tier)

---

## Reports

### `summary [--date YYYY-MM-DD]`
Get nutrition summary for a specific date (or today).

**Output:**
```json
{
  "date": "2026-05-26",
  "total_kcal": 2150.50,
  "target_kcal": 2500.00,
  "kcal_remaining": 349.50,
  "macros": {
    "kcal": 2150.50,
    "protein_g": 85.25,
    "fat_g": 62.75,
    "carbs_g": 285.00,
    "saturated_fat_g": 20.50,
    "sugar_g": 35.25,
    "sodium_mg": 2850.00,
    "fibre_g": 28.00
  },
  "target_macros": {
    "kcal": 2500.00,
    "protein_g": 150.00,
    "fat_g": 80.00,
    "carbs_g": 300.00
  },
  "water_ml": 2000,
  "entry_count_by_meal": {
    "breakfast": 2,
    "lunch": 1,
    "dinner": 1,
    "snack": 0
  }
}
```

### `today`
Get detailed breakdown of today's meals with all entries listed.

**Output:**
```json
{
  "date": "2026-05-26",
  "entries": [
    {
      "id": 1,
      "meal_category": "breakfast",
      "display_name": "Test Porridge × 1 serve",
      "kcal": "450.50",
      "protein_g": "15.25",
      "fat_g": "10.75",
      "carbs_g": "75.00",
      "logged_at": "2026-05-26T07:30:00+10:00"
    }
  ],
  "totals": {
    "kcal": "450.50",
    "protein_g": "15.25",
    "fat_g": "10.75",
    "carbs_g": "75.00"
  },
  "water_ml": 1500
}
```

### `week`
Get rolling 7-day nutrition summary.

**Output:**
```json
{
  "from_date": "2026-05-20",
  "to_date": "2026-05-26",
  "days": [
    {
      "date": "2026-05-20",
      "total_kcal": "2300.00",
      "target_kcal": "2500.00",
      "macros": {...},
      "water_ml": 2000
    }
  ],
  "totals": {...},
  "averages": {...},
  "water_ml_total": 14000,
  "water_ml_avg": 2000.0
}
```

---

## Logging Meals

### `log --meal <breakfast|lunch|dinner|snack> --recipe "<name>" [--servings N]`
Log a meal from a saved recipe.

**Examples:**
```bash
nutri_cli.py log --meal breakfast --recipe "Test Porridge" --servings 1
nutri_cli.py log --meal lunch --recipe "Chicken Salad"
```

**Output:**
```json
{
  "id": 42,
  "meal_category": "breakfast",
  "source": "recipe",
  "display_name": "Test Porridge × 1 serve",
  "kcal": "450.50",
  "protein_g": "15.25",
  "fat_g": "10.75",
  "carbs_g": "75.00",
  "logged_at": "2026-05-26T07:30:00+10:00"
}
```

**Exit codes:**
- `0` — success
- `2` — recipe not found
- `1` — other error

### `log --meal <category> --name "<food>" --quantity Q --unit U`
Log food. The API decides where each item's nutrition comes from (your own foods, then Open Food Facts, then an AI estimate run inside nutri-api, else the item fails with a reason). Do not pick a source or search foods first. Calls `POST /meals/log-items`.

Several items in one call: repeat `--item "NAME|QTY|UNIT"` and/or pass `--items-json '[{"name":..,"quantity":..,"unit":..}]'` (up to 20 items; the two forms and `--name` may be combined). A `|` inside NAME is fine because only the last two fields are split off. Quantity must be above 0; unit is one of `g, ml, scoop, item, slice, cup, tsp, tbsp, kg, oz, lb, l`. Not combinable with `--recipe`.

**Examples:**
```bash
nutri_cli.py log --meal lunch --name "meat pie" --quantity 1 --unit item
nutri_cli.py log --meal lunch --item "meat pie|1|item" --item "cola|375|ml"
nutri_cli.py log --meal lunch --items-json '[{"name":"meat pie","quantity":1,"unit":"item"}]' --person Henry
```

**Output:** the API response, printed unchanged:
```json
{
  "meal_category": "lunch",
  "person": "George",
  "logged_count": 1,
  "failed_count": 1,
  "items": [
    {"name": "meat pie", "status": "logged", "source_tier": "open_food_facts",
     "matched_food_name": "Meat Pie", "matched_brand": "Mrs Mac's", "meal_id": 51,
     "kcal": 320.0, "estimated": false, "confidence": null, "notes": [], "error": null},
    {"name": "mystery", "status": "failed", "source_tier": null, "meal_id": null,
     "error": {"error": "AIEstimateError", "detail": "...", "code": "AI_NO_RESULT"}}
  ]
}
```
`source_tier` is `own_food`, `open_food_facts` or `ai_estimate`.

**Exit codes:**
- `0` — every item logged
- `3` — at least one item failed with `AI_NO_RESULT` or `AI_ESTIMATE_FAILED` (JSON still on stdout; the other items were logged)
- `1` — other failure (network, 5xx, an `INTERNAL_ERROR` item, invalid arguments)
- `2` — unknown `--person` (`PERSON_NOT_FOUND`, JSON on stderr)

nutri-api needs the OneCLI credential gateway set up for the AI tier; see `docs/operations.md`.

### `water --ml <int>`
Log water intake in ml.

**Example:**
```bash
nutri_cli.py water --ml 500
```

**Output:**
```json
{
  "id": 1,
  "volume_ml": 500,
  "logged_at": "2026-05-26T10:15:00+10:00"
}
```

---

## Recipe Management

### `recipe list`
List all saved recipes.

**Output:**
```json
[
  {
    "id": 1,
    "name": "Test Porridge",
    "default_meal_category": "breakfast",
    "notes": "Quick breakfast",
    "created_at": "2026-05-12T10:00:00+10:00",
    "updated_at": "2026-05-12T10:00:00+10:00"
  }
]
```

### `recipe show "<name>"`
Show a specific recipe with ingredient list and computed totals.

**Output:**
```json
{
  "id": 1,
  "name": "Test Porridge",
  "default_meal_category": "breakfast",
  "notes": "Quick breakfast",
  "ingredients": [
    {
      "id": 1,
      "recipe_id": 1,
      "food_id": 5,
      "quantity": "50",
      "unit": "g",
      "display_order": 0
    }
  ],
  "kcal": "189.50",
  "protein_g": "6.75",
  "fat_g": "3.25",
  "carbs_g": "33.85",
  "created_at": "2026-05-12T10:00:00+10:00",
  "updated_at": "2026-05-12T10:00:00+10:00"
}
```

### `recipe save "<name>" --ingredients "name1:qty+unit,name2:qty+unit,..." [--meal breakfast|lunch|dinner|snack]`
Save a new recipe with ingredients.

**Examples:**
```bash
nutri_cli.py recipe save "Test Porridge" --ingredients "oats:50g,greek yogurt:100g,banana:1 item" --meal breakfast
```

**On success:**
```json
{
  "id": 1,
  "name": "Test Porridge",
  "default_meal_category": "breakfast",
  "ingredients": [...]
}
```

**If ingredients are missing (exit code 2):**
```json
{
  "status": "missing_foods",
  "missing": ["VPA Isolate Protein", "Almonds"]
}
```

### `recipe delete "<name-or-id>"`
Delete a recipe (soft delete — old logs still reference it).

**Output:**
```json
{
  "status": "deleted",
  "recipe_id": 1
}
```

---

## Food Management

### `food list [--search <term>]`
List all foods (non-deleted).

**Output:**
```json
[
  {
    "id": 1,
    "name": "Oats",
    "serving_type": "per_100g",
    "kcal": "379.00",
    "protein_g": "13.50",
    "fat_g": "6.50",
    "carbs_g": "67.70",
    "entry_type": "food"
  }
]
```

### `food show "<name-or-id>"`
Show a specific food.

**Output:** Same as individual food object in list.

### `food add-manual --name <name> --serving-type <type> --kcal N --protein N --fat N --carbs N [--saturated-fat N --sugar N --sodium-mg N --fibre N --entry-type food|drink]`
Add a food manually.

**Example:**
```bash
nutri_cli.py food add-manual --name "Oats" --serving-type per_100g --kcal 379 --protein 13.5 --fat 6.5 --carbs 67.7 --fibre 10.6
```

**Output:**
```json
{
  "id": 1,
  "name": "Oats",
  "source": "manual",
  "serving_type": "per_100g",
  "kcal": "379.00",
  "protein_g": "13.50",
  "fat_g": "6.50",
  "carbs_g": "67.70",
  "entry_type": "food",
  "created_at": "2026-05-26T10:00:00+10:00"
}
```

### `food add-from-ocr --name <name> --serving-type <type> --kcal N ... [--entry-type food|drink]`
Add a food from OCR confirmation (source will be set to `photo_ocr`).

**Example (used after photo OCR):**
```bash
nutri_cli.py food add-from-ocr --name "Milo Cereal Bar" --serving-type per_100g --kcal 450 --protein 8.5 --fat 12.0 --carbs 72.5 --saturated-fat 5.5 --sugar 25.0
```

**Output:** Same as add-manual but with `source: "photo_ocr"`.

### `food delete <name-or-id>`
Delete a food (soft delete).

**Output:**
```json
{
  "status": "deleted",
  "food_id": 1
}
```

---

## Photo OCR

### `photo --meal <category> --image-path <path>` OR `photo --meal <category> --image-base64 <data>`
Extract nutrition from a food label photo. Claude (the `claude` CLI in the container, signed in through the OneCLI gateway) reads the image; no API key is needed.

**Example:**
```bash
nutri_cli.py photo --meal breakfast --image-path /tmp/label.jpg
```

**On success (for skill to ask confirmation):**
```json
{
  "status": "extracted",
  "name": "Milo Cereal Bar",
  "serving_type": "per_100g",
  "serving_size": 100,
  "serving_unit": "g",
  "kcal": 450.0,
  "protein_g": 8.5,
  "fat_g": 12.0,
  "carbs_g": 72.5,
  "saturated_fat_g": 5.5,
  "sugar_g": 25.0,
  "sodium_mg": 180.0,
  "fibre_g": 6.0,
  "confidence": 0.95,
  "raw_response": "..."
}
```

**On failure (exit code 3):**
```json
{
  "error": "OCR_FAILED",
  "code": 3,
  "message": "Vision model returned invalid JSON"
}
```

---

## Targets

### `target show`
Show the active daily target (for today).

**Output:**
```json
{
  "id": 1,
  "effective_from": "2026-05-20",
  "kcal_target": "2500.00",
  "protein_g_target": "150.00",
  "fat_g_target": "80.00",
  "carbs_g_target": "300.00",
  "created_at": "2026-05-20T10:00:00+10:00"
}
```

### `target set --kcal N [--protein N --fat N --carbs N]`
Set a new daily target (effective from today).

**Example:**
```bash
nutri_cli.py target set --kcal 2500 --protein 150 --fat 80 --carbs 300
```

**Output:** Same as show.

---

## Editing & Deleting

### `edit <log_id> [--servings N] [--meal category] [--kcal N --protein N --fat N --carbs N --saturated-fat N --sugar N --sodium-mg N --fibre N] [--notes "..."]`
Edit a logged meal entry.

**Example:**
```bash
nutri_cli.py edit 42 --kcal 500 --protein 20 --fat 15 --carbs 80
```

**Output:**
```json
{
  "id": 42,
  "meal_category": "breakfast",
  "display_name": "Test Porridge × 1 serve",
  "kcal": "500.00",
  "protein_g": "20.00",
  "fat_g": "15.00",
  "carbs_g": "80.00",
  "updated_at": "2026-05-26T07:45:00+10:00"
}
```

### `delete <log_id>`
Delete a logged meal entry (hard delete).

**Output:**
```json
{
  "status": "deleted",
  "log_id": 42
}
```

---

## Meal Status

### `check-meal --meal <breakfast|lunch|dinner|snack> [--date YYYY-MM-DD]`
Check if a meal category is logged for a date.

**On logged (exit 0):**
```json
{
  "status": "logged",
  "kcal_subtotal": "450.50",
  "entry_count": 1,
  "logged": true
}
```

**On missing (exit 0):**
```json
{
  "status": "missing",
  "meal": "lunch",
  "logged": false,
  "entry_count": 0,
  "kcal_subtotal": "0"
}
```

---

## Help

### `help`
Show all available commands and their descriptions.
