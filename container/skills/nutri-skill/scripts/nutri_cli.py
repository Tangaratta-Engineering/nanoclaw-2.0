#!/usr/bin/env python3
"""
Nutrition Tracker CLI

Main interface for logging meals, managing recipes/foods, and viewing reports.
All output is JSON to stdout; errors go to stderr.
"""

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
import pytz

try:
    from dotenv import load_dotenv

    # Load .env from the project root (parent of nutri-skill/scripts/)
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

# Configuration
# Default is the compose service name on the hp-server.home Docker network, which is
# where NanoClaw agent containers run. On the host, set NUTRI_API_URL=http://localhost:9000.
NUTRI_API_URL = os.getenv("NUTRI_API_URL") or "http://nutri-api:8000"
TZ = pytz.timezone("Australia/Sydney")

# Exit codes
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_MISSING_PREREQ = 2
EXIT_AI_FAILURE = 3
EXIT_FOOD_NEEDS_ESTIMATE = 4

# Macro fields from an AI estimate that POST /meals accepts
ESTIMATE_MACRO_FIELDS = (
    "kcal",
    "protein_g",
    "fat_g",
    "saturated_fat_g",
    "carbs_g",
    "sugar_g",
    "sodium_mg",
    "fibre_g",
)


def get_today_sydney() -> date:
    """Get today's date in Sydney timezone."""
    return datetime.now(TZ).date()


def api_call(
    method: str,
    path: str,
    json_data: Optional[Dict] = None,
    params: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Make an API call to the nutrition backend.

    Args:
        method: HTTP method (GET, POST, PATCH, DELETE)
        path: API path (e.g., "/foods", "/meals/42")
        json_data: Request body (for POST/PATCH)
        params: Query parameters

    Returns:
        Response JSON as dict

    Raises:
        httpx.HTTPError on connection failure
        json.JSONDecodeError on invalid response
    """
    url = f"{NUTRI_API_URL}{path}"
    timeout = httpx.Timeout(60.0 if json_data or "estimate" in path else 10.0)

    # trust_env=False: the nutrition API is an internal service. NanoClaw agent containers
    # set HTTP(S)_PROXY to a credential gateway that cannot resolve `nutri-api`, so honouring
    # the proxy variables makes every call fail. (AI estimates run the claude CLI, which has its own proxy settings.)
    with httpx.Client(timeout=timeout, trust_env=False) as client:
        response = client.request(method, url, json=json_data, params=params)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError:
            _exit_on_person_not_found(response)
            raise
        return response.json() if response.content else {}


def _error_body(response: httpx.Response) -> dict[str, Any]:
    """Return the API's JSON error body, or {} if it is not a JSON object."""
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _exit_on_person_not_found(response: httpx.Response) -> None:
    """Exit 2 with the known names so the agent can ask the user to confirm.

    Exits via SystemExit, which the per-command `except Exception` blocks don't
    swallow, so every command that sends `person` gets this behaviour.
    """
    body = _error_body(response)
    if body.get("code") != "PERSON_NOT_FOUND":
        return
    print(
        json.dumps(
            {
                "error": body.get("detail") or "Person not found",
                "code": "PERSON_NOT_FOUND",
                "known_persons": body.get("known_persons", []),
            }
        ),
        file=sys.stderr,
    )
    sys.exit(EXIT_MISSING_PREREQ)


def with_person(args, data: dict | None = None) -> dict:
    """Return `data` (copied) plus `person` when --person was given.

    Use for query params (GET) and JSON bodies (POST) on per-person endpoints.
    """
    result = dict(data) if data else {}
    person = getattr(args, "person", None)
    if person:
        result["person"] = person
    return result


def output_json(data: Dict[str, Any], exit_code: int = EXIT_SUCCESS):
    """Output JSON to stdout and exit."""
    print(json.dumps(data, default=str))
    sys.exit(exit_code)


def error_json(message: str, code: int = "ERROR", exit_code: int = EXIT_ERROR):
    """Output error JSON to stderr and exit."""
    error_data = {"error": message, "code": code}
    print(json.dumps(error_data), file=sys.stderr)
    sys.exit(exit_code)


# ============================================================================
# Subcommand Handlers
# ============================================================================


def cmd_help(args) -> None:
    """Show help information for all commands."""
    help_text = {
        "status": "ok",
        "commands": [
            {
                "category": "Reports",
                "items": [
                    {
                        "command": "nutri_summary",
                        "description": "Today's totals (kcal, macros, water)",
                    },
                    {
                        "command": "nutri_today",
                        "description": "Detailed breakdown of today's meals",
                    },
                    {
                        "command": "nutri_week",
                        "description": "Last 7 days daily totals",
                    },
                ],
            },
            {
                "category": "Logging",
                "items": [
                    {
                        "command": "nutri_log",
                        "description": "Log a meal",
                        "usage": "<meal_type> <food> [qty] [unit]",
                    },
                    {
                        "command": "nutri_photo",
                        "description": "OCR a nutrition label photo",
                        "usage": "<meal_type>",
                    },
                    {
                        "command": "nutri_water",
                        "description": "Log water intake",
                        "usage": "<volume_ml>",
                    },
                    {
                        "command": "nutri_weight",
                        "description": "Log body weight in kg (or: history, delete)",
                        "usage": "<kg> | history [days] | delete <id>",
                    },
                ],
            },
            {
                "category": "Lookup",
                "items": [
                    {
                        "command": "nutri_check_meal",
                        "description": "View a specific meal",
                        "usage": "<meal_id>",
                    },
                ],
            },
            {
                "category": "Management",
                "items": [
                    {
                        "command": "nutri_edit",
                        "description": "Edit meal macros",
                        "usage": "<meal_id> <field> <value>",
                    },
                    {
                        "command": "nutri_delete",
                        "description": "Delete a meal",
                        "usage": "<meal_id>",
                    },
                    {
                        "command": "nutri_recipe",
                        "description": "Manage recipes",
                        "usage": "[list|show|save|delete]",
                    },
                    {
                        "command": "nutri_food",
                        "description": "Manage foods",
                        "usage": "[list|show|add-manual|delete]",
                    },
                    {
                        "command": "nutri_target",
                        "description": "View or set daily targets",
                        "usage": "[show|set]",
                    },
                ],
            },
            {
                "category": "People",
                "items": [
                    {
                        "command": "nutri_person",
                        "description": "List or add people (add needs confirmation). "
                        "Add --person NAME to log or report for someone else",
                        "usage": "[list|add <name>]",
                    },
                ],
            },
            {
                "category": "Help",
                "items": [
                    {"command": "nutri_help", "description": "Show this help message"},
                ],
            },
        ],
    }
    output_json(help_text)


def cmd_log(args) -> None:
    """Log a meal (recipe, food, or free-text estimate)."""
    try:
        # Determine source and collect data
        if args.recipe:
            # Log from recipe
            recipes = api_call("GET", "/recipes", params={"search": args.recipe})
            if not recipes:
                error_json(
                    f"Recipe not found: {args.recipe}",
                    "RECIPE_NOT_FOUND",
                    EXIT_MISSING_PREREQ,
                )

            recipe = recipes[0]
            payload = {
                "meal_category": args.meal,
                "source": "recipe",
                "recipe_id": recipe["id"],
                "servings": float(args.servings or 1),
            }

        elif args.food:
            # Log from food
            foods = api_call("GET", "/foods", params={"search": args.food})
            if not foods:
                error_json(
                    f"Food not found: {args.food}",
                    "FOOD_NOT_FOUND",
                    EXIT_MISSING_PREREQ,
                )

            food = foods[0]
            payload = {
                "meal_category": args.meal,
                "source": "food",
                "food_id": food["id"],
                "quantity": float(args.quantity or 1),
                "unit": args.unit or "serving",
            }

        elif args.estimate:
            # AI estimation (calls Claude)
            from ai_estimate import call_text_estimation

            try:
                estimate = call_text_estimation(args.estimate, "")
            except Exception as e:
                error_json(f"AI estimation failed: {e}", "AI_FAILURE", EXIT_AI_FAILURE)

            payload = {
                "meal_category": args.meal,
                "source": "ai_estimate",
                "free_text_description": args.estimate,
                **estimate,
            }
        else:
            error_json("Must provide --recipe, --food, or --estimate", "MISSING_SOURCE")

        # Create meal log
        meal = api_call("POST", "/meals", with_person(args, payload))
        output_json(meal)

    except Exception as e:
        error_json(str(e), "LOG_ERROR")


def cmd_resolve_items(args) -> None:
    """Batch resolve and log a structured meal."""
    try:
        # Parse items: either a JSON array string or individual --item flags
        if args.items_json:
            try:
                items = json.loads(args.items_json)
            except json.JSONDecodeError as e:
                error_json(f"Invalid JSON for --items: {e}", "INVALID_JSON")
                return
        else:
            error_json("Must provide --items JSON", "MISSING_ITEMS")
            return

        if not items:
            error_json("No items provided. Use --items JSON array.", "MISSING_ITEMS")
            return

        # Step 1: call resolve-items endpoint
        payload = {"meal_category": args.meal, "items": items}
        resolve_result = api_call("POST", "/meals/resolve-items", payload)

        logged_meals = []
        estimation_failures = []

        # Step 2: log resolved items
        for item in resolve_result.get("resolved", []):
            meal_payload = {
                "meal_category": args.meal,
                "source": "food",
                "food_id": item["food_id"],
                "quantity": item["quantity"],
                "unit": item["unit"],
            }
            meal = api_call("POST", "/meals", with_person(args, meal_payload))
            logged_meals.append(
                {
                    "name": item["name"],
                    "source": item["source"],
                    "meal_id": meal.get("id"),
                    "kcal": float(meal.get("kcal", 0)),
                    "protein_g": float(meal.get("protein_g", 0)),
                }
            )

        # Step 3: items found nowhere. The AI estimate is the last resort, so log it
        # straight away (flagged as an estimate) rather than asking the user first.
        estimation_failures = []
        for item in resolve_result.get("needs_estimation", []):
            description = f"{item['name']}, {item['quantity']} {item['unit']}"
            try:
                from ai_estimate import call_text_estimation

                estimate = call_text_estimation(description, "")
            except Exception as e:
                estimation_failures.append(
                    {
                        "name": item["name"],
                        "quantity": item["quantity"],
                        "unit": item["unit"],
                        "reason": str(e),
                    }
                )
                continue

            meal_payload = {
                "meal_category": args.meal,
                "source": "ai_estimate",
                "free_text_description": description,
                "display_name": item["name"],
                "notes": f"AI estimate ({estimate.get('confidence', 'low')} confidence)",
                **{k: v for k, v in estimate.items() if k in ESTIMATE_MACRO_FIELDS},
            }
            meal = api_call("POST", "/meals", with_person(args, meal_payload))
            logged_meals.append(
                {
                    "name": item["name"],
                    "source": "ai_estimate",
                    "estimated": True,
                    "confidence": estimate.get("confidence", "low"),
                    "meal_id": meal.get("id"),
                    "kcal": float(meal.get("kcal", 0)),
                    "protein_g": float(meal.get("protein_g", 0)),
                }
            )

        output_data = {
            "status": "ok",
            "meal_category": args.meal,
            "logged": logged_meals,
        }
        if estimation_failures:
            output_data["estimation_failures"] = estimation_failures
            output_json(output_data, EXIT_AI_FAILURE)
        output_json(output_data)

    except Exception as e:
        error_json(str(e), "RESOLVE_ITEMS_ERROR")


def cmd_photo(args) -> None:
    """OCR a nutrition label photo and extract nutrition data."""
    try:
        from ai_estimate import call_vision, EstimateError

        # Load image data
        image_bytes = None
        if args.image_path:
            with open(args.image_path, "rb") as f:
                image_bytes = f.read()
        elif args.image_base64:
            import base64

            image_bytes = base64.standard_b64decode(args.image_base64)
        else:
            error_json("Must provide --image-path or --image-base64", "MISSING_IMAGE")

        # Call vision model
        try:
            nutrition = call_vision(image_bytes, "")
        except EstimateError as e:
            error_json(str(e), "OCR_FAILED", EXIT_AI_FAILURE)

        # For high-confidence extractions, auto-log the meal
        if nutrition.get("confidence") == "high" and args.auto_log:
            payload = {
                "meal_category": args.meal,
                "source": "photo_ocr",
                "product_name": nutrition.get("product_name"),
                "brand": nutrition.get("brand"),
                "kcal": float(nutrition.get("kcal", 0)),
                "protein_g": float(nutrition.get("protein_g", 0)),
                "fat_g": float(nutrition.get("fat_g", 0)),
                "carbs_g": float(nutrition.get("carbs_g", 0)),
            }
            if nutrition.get("saturated_fat_g"):
                payload["saturated_fat_g"] = float(nutrition.get("saturated_fat_g"))
            if nutrition.get("sugar_g"):
                payload["sugar_g"] = float(nutrition.get("sugar_g"))
            if nutrition.get("sodium_mg"):
                payload["sodium_mg"] = float(nutrition.get("sodium_mg"))
            if nutrition.get("fibre_g"):
                payload["fibre_g"] = float(nutrition.get("fibre_g"))

            meal = api_call("POST", "/meals", with_person(args, payload))
            output_json(
                {
                    "status": "logged",
                    "meal_id": meal.get("id"),
                    "meal_type": args.meal,
                    "product_name": nutrition.get("product_name"),
                    "kcal": nutrition.get("kcal"),
                    "protein_g": nutrition.get("protein_g"),
                    "logged_at": meal.get("logged_at"),
                }
            )
        else:
            # Return extracted nutrition awaiting confirmation (low confidence or manual confirmation requested)
            output_json(
                {
                    "status": "extracted",
                    "meal_type": args.meal,
                    "product_name": nutrition.get("product_name"),
                    "brand": nutrition.get("brand"),
                    "kcal": nutrition.get("kcal"),
                    "protein_g": nutrition.get("protein_g"),
                    "fat_g": nutrition.get("fat_g"),
                    "carbs_g": nutrition.get("carbs_g"),
                    "saturated_fat_g": nutrition.get("saturated_fat_g"),
                    "sugar_g": nutrition.get("sugar_g"),
                    "sodium_mg": nutrition.get("sodium_mg"),
                    "fibre_g": nutrition.get("fibre_g"),
                    "confidence": nutrition.get("confidence", "low"),
                    "note": (
                        "Low confidence. Please review the extracted data. Use /nutri_log to manually enter this meal if incorrect."
                        if nutrition.get("confidence") == "low"
                        else None
                    ),
                }
            )

    except FileNotFoundError:
        error_json(f"Image file not found: {args.image_path}", "FILE_NOT_FOUND")
    except Exception as e:
        error_json(str(e), "PHOTO_ERROR")


def cmd_water(args) -> None:
    """Log water intake."""
    try:
        water = api_call("POST", "/water", with_person(args, {"volume_ml": args.ml}))
        output_json(water)
    except Exception as e:
        error_json(str(e), "WATER_ERROR")


def cmd_weight(args) -> None:
    """Log a body weight entry (kg)."""
    if args.kg is None:
        error_json(
            "Provide --kg, or use 'weight history' / 'weight delete ID'", "MISSING_KG"
        )
    payload: dict[str, Any] = {"weight_kg": args.kg}
    if args.at:
        payload["logged_at"] = args.at
    try:
        output_json(api_call("POST", "/weight", with_person(args, payload)))
    except Exception as e:
        error_json(str(e), "WEIGHT_ERROR")


def cmd_weight_history(args) -> None:
    """Show weight entries and summary for the last N days."""
    try:
        params = with_person(args, {"days": args.days})
        output_json(api_call("GET", "/weight", params=params))
    except Exception as e:
        error_json(str(e), "WEIGHT_HISTORY_ERROR")


def cmd_weight_delete(args) -> None:
    """Delete a weight entry by ID."""
    try:
        api_call("DELETE", f"/weight/{args.weight_id}")
        output_json({"status": "deleted", "weight_id": args.weight_id})
    except Exception as e:
        error_json(str(e), "WEIGHT_DELETE_ERROR")


def cmd_person_list(args) -> None:
    """List known people."""
    try:
        output_json({"persons": api_call("GET", "/persons")})
    except Exception as e:
        error_json(str(e), "PERSON_LIST_ERROR")


def cmd_person_add(args) -> None:
    """Create a person. Only run after the user has explicitly confirmed."""
    try:
        output_json(api_call("POST", "/persons", {"name": args.name}))
    except httpx.HTTPStatusError as e:
        # DUPLICATE_ERROR / PERSON_LIMIT_REACHED / VALIDATION_FAILED: exit 1
        body = _error_body(e.response)
        error_json(
            body.get("detail") or str(e),
            body.get("code", "PERSON_ADD_ERROR"),
        )
    except Exception as e:
        error_json(str(e), "PERSON_ADD_ERROR")


def cmd_today(args) -> None:
    """Show today's meals and water."""
    try:
        report = api_call("GET", "/reports/today", params=with_person(args))
        output_json(report)
    except Exception as e:
        error_json(str(e), "TODAY_ERROR")


def cmd_summary(args) -> None:
    """Show today's summary vs target."""
    try:
        query_date = args.date or get_today_sydney().isoformat()
        report = api_call(
            "GET", "/reports/summary", params=with_person(args, {"date": query_date})
        )
        output_json(report)
    except Exception as e:
        error_json(str(e), "SUMMARY_ERROR")


def cmd_week(args) -> None:
    """Show rolling 7-day summary."""
    try:
        report = api_call("GET", "/reports/week", params=with_person(args))
        output_json(report)
    except Exception as e:
        error_json(str(e), "WEEK_ERROR")


def cmd_recipe_list(args) -> None:
    """List recipes."""
    try:
        recipes = api_call("GET", "/recipes")
        output_json({"recipes": recipes})
    except Exception as e:
        error_json(str(e), "RECIPE_LIST_ERROR")


def cmd_recipe_show(args) -> None:
    """Show recipe details."""
    try:
        recipes = api_call("GET", "/recipes", params={"search": args.name})
        if not recipes:
            error_json(f"Recipe not found: {args.name}", "RECIPE_NOT_FOUND")
        output_json(recipes[0])
    except Exception as e:
        error_json(str(e), "RECIPE_SHOW_ERROR")


def cmd_recipe_save(args) -> None:
    """Save a new recipe."""
    try:
        # Parse ingredients
        ingredients = []
        if args.ingredients:
            for ingredient_str in args.ingredients.split(","):
                parts = ingredient_str.strip().split(":")
                if len(parts) != 2:
                    error_json(
                        f"Invalid ingredient format: {ingredient_str}", "INVALID_FORMAT"
                    )
                food_name, qty_unit = parts
                # Parse quantity and unit
                qty_parts = qty_unit.rsplit(maxsplit=1)
                if len(qty_parts) != 2:
                    error_json(f"Invalid quantity format: {qty_unit}", "INVALID_FORMAT")
                quantity, unit = qty_parts

                # Resolve food by name
                foods = api_call("GET", "/foods", params={"search": food_name})
                if not foods:
                    error_json(
                        f"Food not found: {food_name}",
                        "FOOD_NOT_FOUND",
                        EXIT_MISSING_PREREQ,
                    )

                ingredients.append(
                    {
                        "food_id": foods[0]["id"],
                        "quantity": float(quantity),
                        "unit": unit,
                    }
                )

        payload = {
            "name": args.name,
            "ingredients": ingredients,
        }
        if args.meal:
            payload["default_meal_category"] = args.meal

        recipe = api_call("POST", "/recipes", payload)
        output_json(recipe)

    except Exception as e:
        error_json(str(e), "RECIPE_SAVE_ERROR")


def cmd_recipe_delete(args) -> None:
    """Delete a recipe."""
    try:
        # Try parsing as ID first
        try:
            recipe_id = int(args.name_or_id)
        except ValueError:
            # Search by name
            recipes = api_call("GET", "/recipes", params={"search": args.name_or_id})
            if not recipes:
                error_json(f"Recipe not found: {args.name_or_id}", "RECIPE_NOT_FOUND")
            recipe_id = recipes[0]["id"]

        api_call("DELETE", f"/recipes/{recipe_id}")
        output_json({"status": "deleted", "recipe_id": recipe_id})

    except Exception as e:
        error_json(str(e), "RECIPE_DELETE_ERROR")


def cmd_food_list(args) -> None:
    """List foods with optional search."""
    try:
        params = {}
        if args.search:
            params["search"] = args.search
        foods = api_call("GET", "/foods", params=params)
        output_json({"foods": foods})
    except Exception as e:
        error_json(str(e), "FOOD_LIST_ERROR")


def cmd_food_show(args) -> None:
    """Show food details."""
    try:
        # Try parsing as ID first
        try:
            food_id = int(args.name_or_id)
            food = api_call("GET", f"/foods/{food_id}")
        except ValueError:
            # Search by name
            foods = api_call("GET", "/foods", params={"search": args.name_or_id})
            if not foods:
                error_json(f"Food not found: {args.name_or_id}", "FOOD_NOT_FOUND")
            food = foods[0]

        output_json(food)

    except Exception as e:
        error_json(str(e), "FOOD_SHOW_ERROR")


def cmd_food_add_manual(args) -> None:
    """Add food manually."""
    try:
        payload = {
            "name": args.name,
            "source": "manual",
            "serving_type": args.serving_type,
            "kcal": float(args.kcal),
            "protein_g": float(args.protein),
            "fat_g": float(args.fat),
            "carbs_g": float(args.carbs),
        }

        if args.serving_type == "per_serving":
            if not args.serving_size or not args.serving_unit:
                error_json(
                    "per_serving foods require --serving-size and --serving-unit",
                    "MISSING_SERVING_INFO",
                )
            payload["serving_size"] = float(args.serving_size)
            payload["serving_unit"] = args.serving_unit

        if args.saturated_fat:
            payload["saturated_fat_g"] = float(args.saturated_fat)
        if args.sugar:
            payload["sugar_g"] = float(args.sugar)
        if args.sodium_mg:
            payload["sodium_mg"] = float(args.sodium_mg)
        if args.fibre:
            payload["fibre_g"] = float(args.fibre)

        payload["entry_type"] = args.entry_type or "food"

        food = api_call("POST", "/foods", payload)
        output_json(food)

    except Exception as e:
        error_json(str(e), "FOOD_ADD_ERROR")


def cmd_food_add_from_ocr(args) -> None:
    """Add food from OCR confirmation (after photo extraction)."""
    try:
        payload = {
            "name": args.name,
            "source": "photo_ocr",
            "serving_type": args.serving_type,
            "kcal": float(args.kcal),
            "protein_g": float(args.protein),
            "fat_g": float(args.fat),
            "carbs_g": float(args.carbs),
        }

        if args.serving_type == "per_serving":
            if not args.serving_size or not args.serving_unit:
                error_json(
                    "per_serving foods require --serving-size and --serving-unit",
                    "MISSING_SERVING_INFO",
                )
                return
            payload["serving_size"] = float(args.serving_size)
            payload["serving_unit"] = args.serving_unit

        if args.saturated_fat:
            payload["saturated_fat_g"] = float(args.saturated_fat)
        if args.sugar:
            payload["sugar_g"] = float(args.sugar)
        if args.sodium_mg:
            payload["sodium_mg"] = float(args.sodium_mg)
        if args.fibre:
            payload["fibre_g"] = float(args.fibre)

        payload["entry_type"] = args.entry_type or "food"

        food = api_call("POST", "/foods", payload)
        output_json(food)

    except Exception as e:
        error_json(str(e), "FOOD_ADD_OCR_ERROR")


def cmd_food_delete(args) -> None:
    """Delete a food."""
    try:
        # Try parsing as ID first
        try:
            food_id = int(args.name_or_id)
        except ValueError:
            # Search by name
            foods = api_call("GET", "/foods", params={"search": args.name_or_id})
            if not foods:
                error_json(f"Food not found: {args.name_or_id}", "FOOD_NOT_FOUND")
            food_id = foods[0]["id"]

        api_call("DELETE", f"/foods/{food_id}")
        output_json({"status": "deleted", "food_id": food_id})

    except Exception as e:
        error_json(str(e), "FOOD_DELETE_ERROR")


def cmd_target_show(args) -> None:
    """Show active daily target."""
    try:
        target = api_call("GET", "/targets/active", params=with_person(args))
        output_json(target)
    except Exception as e:
        error_json(str(e), "TARGET_SHOW_ERROR")


def cmd_target_set(args) -> None:
    """Set daily calorie target."""
    try:
        payload = {"kcal_target": float(args.kcal)}
        if args.protein:
            payload["protein_g_target"] = float(args.protein)
        if args.fat:
            payload["fat_g_target"] = float(args.fat)
        if args.carbs:
            payload["carbs_g_target"] = float(args.carbs)

        target = api_call("POST", "/targets", with_person(args, payload))
        output_json(target)

    except Exception as e:
        error_json(str(e), "TARGET_SET_ERROR")


def cmd_edit(args) -> None:
    """Edit a meal log entry."""
    try:
        payload = {}
        if args.servings:
            payload["servings"] = float(args.servings)
        if args.meal:
            payload["meal_category"] = args.meal
        if args.kcal:
            payload["kcal"] = float(args.kcal)
        if args.protein:
            payload["protein_g"] = float(args.protein)
        if args.fat:
            payload["fat_g"] = float(args.fat)
        if args.carbs:
            payload["carbs_g"] = float(args.carbs)
        if args.notes:
            payload["notes"] = args.notes

        meal = api_call("PATCH", f"/meals/{args.log_id}", payload)
        output_json(meal)

    except Exception as e:
        error_json(str(e), "EDIT_ERROR")


def cmd_delete(args) -> None:
    """Delete a meal log entry."""
    try:
        api_call("DELETE", f"/meals/{args.log_id}")
        output_json({"status": "deleted", "log_id": args.log_id})
    except Exception as e:
        error_json(str(e), "DELETE_ERROR")


def cmd_check_meal(args) -> None:
    """Check if a meal is logged today (used by cron)."""
    try:
        today = get_today_sydney().isoformat()
        status = api_call(
            "GET",
            "/reports/meal-status",
            params=with_person(args, {"meal_category": args.meal, "date": today}),
        )

        if status["logged"]:
            output_json(
                {
                    "status": "logged",
                    "kcal_subtotal": status["kcal_subtotal"],
                    "entry_count": status["entry_count"],
                }
            )
        else:
            output_json({"status": "missing", "meal": args.meal})

    except Exception as e:
        error_json(str(e), "CHECK_MEAL_ERROR")


# ============================================================================
# Main CLI
# ============================================================================


def main():
    """Parse arguments and dispatch to handlers."""
    parser = argparse.ArgumentParser(
        description="Nutrition Tracker CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--person",
        help="Person to act for (default: George). Also accepted after the subcommand.",
    )
    # Copy for subparsers: SUPPRESS keeps a top-level --person from being
    # overwritten by the subparser's default when the flag is given before the command.
    person_parent = argparse.ArgumentParser(add_help=False)
    person_parent.add_argument(
        "--person", default=argparse.SUPPRESS, help="Person name"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # log command
    log_parser = subparsers.add_parser(
        "log", help="Log a meal", parents=[person_parent]
    )
    log_parser.add_argument(
        "--meal", required=True, choices=["breakfast", "lunch", "dinner", "snack"]
    )
    log_group = log_parser.add_mutually_exclusive_group(required=True)
    log_group.add_argument("--recipe", help="Recipe name")
    log_group.add_argument("--food", help="Food name")
    log_group.add_argument("--estimate", help="Free-text meal description")
    log_parser.add_argument("--servings", help="Number of servings")
    log_parser.add_argument("--quantity", help="Food quantity")
    log_parser.add_argument("--unit", help="Food unit")
    log_parser.set_defaults(func=cmd_log)

    # resolve-items command
    resolve_parser = subparsers.add_parser(
        "resolve-items",
        help="Batch resolve and log a structured meal",
        parents=[person_parent],
    )
    resolve_parser.add_argument(
        "--meal", required=True, choices=["breakfast", "lunch", "dinner", "snack"]
    )
    resolve_parser.add_argument(
        "--items",
        dest="items_json",
        required=True,
        metavar="JSON",
        help='JSON array: \'[{"name":"chicken","quantity":150,"unit":"g"},...]\'',
    )
    resolve_parser.set_defaults(func=cmd_resolve_items)

    # photo command
    photo_parser = subparsers.add_parser(
        "photo", help="OCR nutrition label photo", parents=[person_parent]
    )
    photo_parser.add_argument(
        "--meal", required=True, choices=["breakfast", "lunch", "dinner", "snack"]
    )
    photo_image_group = photo_parser.add_mutually_exclusive_group(required=True)
    photo_image_group.add_argument("--image-path", help="Path to image file")
    photo_image_group.add_argument("--image-base64", help="Image data as base64")
    photo_parser.add_argument(
        "--auto-log", action="store_true", help="Auto-log high-confidence extractions"
    )
    photo_parser.set_defaults(func=cmd_photo)

    # water command
    water_parser = subparsers.add_parser(
        "water", help="Log water", parents=[person_parent]
    )
    water_parser.add_argument("--ml", type=int, required=True, help="Volume in ml")
    water_parser.set_defaults(func=cmd_water)

    # weight command: `weight --kg X [--at ISO]` logs; `weight history|delete` are actions
    weight_parser = subparsers.add_parser(
        "weight", help="Log or view body weight (kg)", parents=[person_parent]
    )
    weight_parser.add_argument("--kg", type=float, help="Body weight in kg")
    weight_parser.add_argument("--at", help="Back-dated ISO timestamp (default: now)")
    weight_parser.set_defaults(func=cmd_weight)
    weight_subparsers = weight_parser.add_subparsers(dest="weight_cmd")

    weight_history = weight_subparsers.add_parser(
        "history", help="Weight over time", parents=[person_parent]
    )
    weight_history.add_argument(
        "--days", type=int, default=30, help="Days back (1-3650)"
    )
    weight_history.set_defaults(func=cmd_weight_history)

    weight_delete = weight_subparsers.add_parser("delete", help="Delete a weight entry")
    weight_delete.add_argument("weight_id", type=int)
    weight_delete.set_defaults(func=cmd_weight_delete)

    # person commands
    person_cmd_parser = subparsers.add_parser("person", help="Manage people")
    person_subparsers = person_cmd_parser.add_subparsers(
        dest="person_cmd", required=True
    )

    person_list = person_subparsers.add_parser("list", help="List people")
    person_list.set_defaults(func=cmd_person_list)

    person_add = person_subparsers.add_parser(
        "add", help="Add a person (only after user confirmation)"
    )
    person_add.add_argument("name", help="Person name")
    person_add.set_defaults(func=cmd_person_add)

    # today command
    today_parser = subparsers.add_parser(
        "today", help="Show today's meals", parents=[person_parent]
    )
    today_parser.set_defaults(func=cmd_today)

    # summary command
    summary_parser = subparsers.add_parser(
        "summary", help="Show daily summary", parents=[person_parent]
    )
    summary_parser.add_argument("--date", help="Date (YYYY-MM-DD)")
    summary_parser.set_defaults(func=cmd_summary)

    # week command
    week_parser = subparsers.add_parser(
        "week", help="Show 7-day summary", parents=[person_parent]
    )
    week_parser.set_defaults(func=cmd_week)

    # recipe commands
    recipe_parser = subparsers.add_parser("recipe", help="Manage recipes")
    recipe_subparsers = recipe_parser.add_subparsers(dest="recipe_cmd", required=True)

    recipe_list = recipe_subparsers.add_parser("list", help="List recipes")
    recipe_list.set_defaults(func=cmd_recipe_list)

    recipe_show = recipe_subparsers.add_parser("show", help="Show recipe")
    recipe_show.add_argument("name", help="Recipe name")
    recipe_show.set_defaults(func=cmd_recipe_show)

    recipe_save = recipe_subparsers.add_parser("save", help="Save recipe")
    recipe_save.add_argument("name", help="Recipe name")
    recipe_save.add_argument(
        "--ingredients",
        required=True,
        help="Ingredients (comma-separated: name:qty+unit)",
    )
    recipe_save.add_argument("--meal", help="Default meal category")
    recipe_save.set_defaults(func=cmd_recipe_save)

    recipe_delete = recipe_subparsers.add_parser("delete", help="Delete recipe")
    recipe_delete.add_argument("name_or_id", help="Recipe name or ID")
    recipe_delete.set_defaults(func=cmd_recipe_delete)

    # food commands
    food_parser = subparsers.add_parser("food", help="Manage foods")
    food_subparsers = food_parser.add_subparsers(dest="food_cmd", required=True)

    food_list = food_subparsers.add_parser("list", help="List foods")
    food_list.add_argument("--search", help="Search term")
    food_list.set_defaults(func=cmd_food_list)

    food_show = food_subparsers.add_parser("show", help="Show food")
    food_show.add_argument("name_or_id", help="Food name or ID")
    food_show.set_defaults(func=cmd_food_show)

    food_add = food_subparsers.add_parser("add-manual", help="Add food manually")
    food_add.add_argument("--name", required=True)
    food_add.add_argument(
        "--serving-type",
        required=True,
        choices=["per_100g", "per_100ml", "per_serving"],
    )
    food_add.add_argument("--serving-size", help="For per_serving")
    food_add.add_argument("--serving-unit", help="For per_serving")
    food_add.add_argument("--kcal", required=True, type=float)
    food_add.add_argument("--protein", required=True, type=float)
    food_add.add_argument("--fat", required=True, type=float)
    food_add.add_argument("--carbs", required=True, type=float)
    food_add.add_argument("--saturated-fat", type=float)
    food_add.add_argument("--sugar", type=float)
    food_add.add_argument("--sodium-mg", type=float)
    food_add.add_argument("--fibre", type=float)
    food_add.add_argument("--entry-type", choices=["food", "drink"])
    food_add.set_defaults(func=cmd_food_add_manual)

    food_add_ocr = food_subparsers.add_parser(
        "add-from-ocr", help="Add food from OCR confirmation"
    )
    food_add_ocr.add_argument("--name", required=True)
    food_add_ocr.add_argument(
        "--serving-type",
        required=True,
        choices=["per_100g", "per_100ml", "per_serving"],
    )
    food_add_ocr.add_argument("--serving-size", help="For per_serving")
    food_add_ocr.add_argument("--serving-unit", help="For per_serving")
    food_add_ocr.add_argument("--kcal", required=True, type=float)
    food_add_ocr.add_argument("--protein", required=True, type=float)
    food_add_ocr.add_argument("--fat", required=True, type=float)
    food_add_ocr.add_argument("--carbs", required=True, type=float)
    food_add_ocr.add_argument("--saturated-fat", type=float)
    food_add_ocr.add_argument("--sugar", type=float)
    food_add_ocr.add_argument("--sodium-mg", type=float)
    food_add_ocr.add_argument("--fibre", type=float)
    food_add_ocr.add_argument("--entry-type", choices=["food", "drink"])
    food_add_ocr.set_defaults(func=cmd_food_add_from_ocr)

    food_delete = food_subparsers.add_parser("delete", help="Delete food")
    food_delete.add_argument("name_or_id", help="Food name or ID")
    food_delete.set_defaults(func=cmd_food_delete)

    # target commands
    target_parser = subparsers.add_parser("target", help="Manage daily targets")
    target_subparsers = target_parser.add_subparsers(dest="target_cmd", required=True)

    target_show = target_subparsers.add_parser(
        "show", help="Show target", parents=[person_parent]
    )
    target_show.set_defaults(func=cmd_target_show)

    target_set = target_subparsers.add_parser(
        "set", help="Set target", parents=[person_parent]
    )
    target_set.add_argument("--kcal", required=True, type=float)
    target_set.add_argument("--protein", type=float)
    target_set.add_argument("--fat", type=float)
    target_set.add_argument("--carbs", type=float)
    target_set.set_defaults(func=cmd_target_set)

    # edit command
    edit_parser = subparsers.add_parser("edit", help="Edit meal log")
    edit_parser.add_argument("log_id", type=int)
    edit_parser.add_argument("--servings", type=float)
    edit_parser.add_argument(
        "--meal", choices=["breakfast", "lunch", "dinner", "snack"]
    )
    edit_parser.add_argument("--kcal", type=float)
    edit_parser.add_argument("--protein", type=float)
    edit_parser.add_argument("--fat", type=float)
    edit_parser.add_argument("--carbs", type=float)
    edit_parser.add_argument("--notes")
    edit_parser.set_defaults(func=cmd_edit)

    # delete command
    delete_parser = subparsers.add_parser("delete", help="Delete meal log")
    delete_parser.add_argument("log_id", type=int)
    delete_parser.set_defaults(func=cmd_delete)

    # check-meal command
    check_parser = subparsers.add_parser(
        "check-meal", help="Check if meal is logged", parents=[person_parent]
    )
    check_parser.add_argument(
        "--meal", required=True, choices=["breakfast", "lunch", "dinner", "snack"]
    )
    check_parser.set_defaults(func=cmd_check_meal)

    # help command
    help_parser = subparsers.add_parser("help", help="Show help information")
    help_parser.set_defaults(func=cmd_help)

    # Parse and dispatch
    args = parser.parse_args()
    if hasattr(args, "func"):
        try:
            args.func(args)
        except Exception as e:
            error_json(str(e), "UNHANDLED_ERROR")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
