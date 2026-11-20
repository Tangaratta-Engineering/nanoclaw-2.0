"""AI estimation for the nutrition skill: label OCR (vision) and meal estimates (text), done by Claude.

Runs the `claude` CLI that every agent container already has (`claude -p`). It signs in the same way the agent itself
does, through the OneCLI gateway, so nothing is read from or needed in the environment: no API key, and no Python
SDK (the image has none). The model can be changed with NUTRI_CLAUDE_MODEL.
"""

import json
import os
import subprocess
import tempfile
from typing import Any, Callable, Dict

MODEL = os.environ.get("NUTRI_CLAUDE_MODEL", "claude-haiku-5-5")
SYSTEM = "You extract nutrition data. Reply with only the JSON object asked for: no markdown, no prose."
# Claude Code does not pass its sign-in placeholder on to the commands an agent runs, so a `claude -p` started from a
# shell command would say "Not logged in". Any value works: the OneCLI gateway swaps in the real credential on the wire.
PLACEHOLDER = "placeholder"
AUTH_HINT = " (Claude could not sign in from this container: the OneCLI gateway's Claude credential is missing or expired, ask George)"


class EstimateError(Exception):
    """AI estimation failed."""

    pass


VISION_PROMPT = """Extract nutrition information from this Australian food label.
Return ONLY valid JSON (no markdown, no prose) matching this schema:
{
  "product_name": "string",
  "brand": "string or null",
  "serving_type": "per_100g | per_100ml | per_serving",
  "serving_size": "number or null (only for per_serving)",
  "serving_unit": "string or null (e.g. 'scoop', 'slice')",
  "kcal": "number",
  "protein_g": "number",
  "fat_g": "number",
  "saturated_fat_g": "number or null",
  "carbs_g": "number",
  "sugar_g": "number or null",
  "sodium_mg": "number or null",
  "fibre_g": "number or null",
  "confidence": "high | medium | low",
  "kj_was_primary": "boolean (true if only kJ shown, convert using kJ/4.184)"
}

If kJ shown but kcal not shown, set kcal = kJ / 4.184 and kj_was_primary = true.
If uncertain, set confidence = 'low'."""

TEXT_PROMPT = """Estimate nutrition for this Australian meal: "__DESCRIPTION__"

Return ONLY valid JSON (no markdown, no prose) matching this schema:
{
  "product_name": "string (meal name)",
  "serving_type": "per_serving",
  "kcal": "number",
  "protein_g": "number",
  "fat_g": "number",
  "saturated_fat_g": "number or null",
  "carbs_g": "number",
  "sugar_g": "number or null",
  "sodium_mg": "number or null",
  "fibre_g": "number (best estimate in grams, 0 if the food has none; never null)",
  "confidence": "high | medium | low"
}

Set confidence = 'low' if uncertain about the meal or ingredients."""


def _claude(prompt: str, image: bytes = b"", timeout: int = 150, runner: Callable = subprocess.run) -> str:
    """One `claude -p` call. With an image, the file is put in a scratch folder and Claude may only read it."""
    with tempfile.TemporaryDirectory(prefix="nutri-") as d:
        cmd = ["claude", "-p", "--model", MODEL, "--output-format", "json", "--no-session-persistence", "--system-prompt", SYSTEM]
        if image:
            ext = "png" if image[:4] == b"\x89PNG" else "webp" if image[8:12] == b"WEBP" else "jpg"
            name = f"label.{ext}"
            with open(os.path.join(d, name), "wb") as f:
                f.write(image)
            prompt = f"Read the image file ./{name} (use the Read tool), then do this.\n\n{prompt}"
            cmd += ["--tools", "Read", "--allowedTools", "Read"]
        else:
            cmd += ["--tools", ""]
        try:
            env = dict(os.environ)
            if not env.get("CLAUDE_CODE_OAUTH_TOKEN") and not env.get("ANTHROPIC_API_KEY") and not env.get("ANTHROPIC_AUTH_TOKEN"):
                env["CLAUDE_CODE_OAUTH_TOKEN"] = PLACEHOLDER
            r = runner(cmd, input=prompt, cwd=d, env=env, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise EstimateError("Claude took too long to answer")
        except FileNotFoundError:
            raise EstimateError("the claude CLI is not installed in this container")
    out = (r.stdout or "").strip()
    try:
        data = json.loads(out)
    except ValueError:
        data = {}
    text = str(data.get("result", "")) if isinstance(data, dict) else ""
    if r.returncode != 0 or (isinstance(data, dict) and data.get("is_error")):
        msg = (text or (r.stderr or "").strip() or out)[:160]
        hint = AUTH_HINT if any(w in msg.lower() for w in ("login", "authenticat", "api key", "oauth", "401", "credential")) else ""
        raise EstimateError(f"Claude error: {msg}{hint}")
    if not text.strip():
        raise EstimateError("Empty response from Claude")
    return text


def _parse_json(text: str) -> Dict[str, Any]:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise EstimateError("Claude did not return JSON")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        raise EstimateError(f"Claude returned invalid JSON: {e}")


def call_vision(image_bytes: bytes, api_key: str = "", model: str = "", runner: Callable = subprocess.run) -> Dict[str, Any]:
    """Extract nutrition from a label photo. `api_key` and `model` are unused (kept so callers need not change)."""
    return _validate_nutrition_schema(_parse_json(_claude(VISION_PROMPT, image=image_bytes, runner=runner)))


def call_text_estimation(description: str, api_key: str = "", model: str = "", runner: Callable = subprocess.run) -> Dict[str, Any]:
    """Estimate nutrition for a meal description. `api_key` and `model` are unused."""
    prompt = TEXT_PROMPT.replace("__DESCRIPTION__", description.replace('"', "'"))
    return _validate_nutrition_schema(_parse_json(_claude(prompt, runner=runner)))


def _validate_nutrition_schema(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and normalize nutrition data from AI response.

    Ensures required fields are present and have correct types.
    """
    required = ["kcal", "protein_g", "fat_g", "carbs_g"]
    for field in required:
        if field not in data:
            raise EstimateError(f"Missing required field: {field}")

    # Normalize numeric fields
    for field in [
        "kcal",
        "protein_g",
        "fat_g",
        "saturated_fat_g",
        "carbs_g",
        "sugar_g",
        "sodium_mg",
        "fibre_g",
    ]:
        if field in data and data[field] is not None:
            data[field] = float(data[field])

    return data
