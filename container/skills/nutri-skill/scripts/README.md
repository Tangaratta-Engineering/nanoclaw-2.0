# Nutrition Tracker CLI Documentation

The `nutri_cli.py` script provides a command-line interface to the Nutrition Tracker API. All output is JSON to stdout; errors go to stderr.

**Exit codes:**
- `0` — success
- `1` — unexpected error (e.g., network timeout)
- `2` — missing prerequisite (e.g., food not found when saving recipe)
- `3` — AI/OCR failure (e.g., vision model returned invalid JSON)

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

### `log --meal <category> --food "<name>" [--quantity Q --unit U]`
Log a meal from a single food.

**Examples:**
```bash
nutri_cli.py log --meal breakfast --food "Oats" --quantity 50 --unit g
nutri_cli.py log --meal snack --food "Banana"
```

**Output:** Same as recipe logging.

**Exit codes:**
- `0` — success
- `2` — food not found
- `1` — other error

### `log --meal <category> --estimate "<free text>"`
Log a meal with AI estimation from free-text description.

**Examples:**
```bash
nutri_cli.py log --meal dinner --estimate "Chicken parmi with fries at the pub"
```

**Output:**
```json
{
  "id": 43,
  "meal_category": "dinner",
  "source": "ai_estimate",
  "display_name": "Chicken parmi with fries at the pub",
  "kcal": "1150.00",
  "protein_g": "45.00",
  "fat_g": "52.00",
  "carbs_g": "120.00",
  "logged_at": "2026-05-26T19:00:00+10:00"
}
```

**Exit codes:**
- `0` — success
- `3` — AI model failed or returned invalid response
- `1` — other error

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
Extract nutrition from a food label photo using OpenRouter vision model.

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
