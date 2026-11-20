"""resolve-items logs unmatched items as AI estimates instead of asking first."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

import nutri_cli
import ai_estimate

RESOLVED = {
    "food_id": 1,
    "quantity": 50,
    "unit": "g",
    "name": "Oats",
    "source": "local_db",
}
MISSING = {"name": "peri peri sauce", "quantity": 60, "unit": "g", "reason": "no match"}
ESTIMATE = {
    "kcal": 150.0,
    "protein_g": 1.0,
    "fat_g": 12.0,
    "carbs_g": 8.0,
    "confidence": "low",
    "serving_type": "per_serving",
}


def run(items, resolve_payload, estimate=None, estimate_error=None, extra=()):
    posted = []

    def api(method, path, data=None, *a, **k):
        if path == "/meals/resolve-items":
            return resolve_payload
        posted.append(data)
        return {
            "id": 10 + len(posted),
            "kcal": data.get("kcal", 180),
            "protein_g": data.get("protein_g", 6),
        }

    est = patch.object(
        ai_estimate,
        "call_text_estimation",
        side_effect=estimate_error,
        return_value=estimate,
    )
    argv = [
        "nutri_cli.py",
        *extra,
        "resolve-items",
        "--meal",
        "lunch",
        "--items",
        json.dumps(items),
    ]
    with patch.object(sys, "argv", argv), patch.object(
        nutri_cli, "api_call", side_effect=api
    ), est as est_mock:
        code = 0
        try:
            nutri_cli.main()
        except SystemExit as e:
            code = e.code
    return code, posted, est_mock


def stdout(capsys):
    return json.loads(capsys.readouterr().out)


def test_unmatched_item_is_estimated_and_logged_without_asking(capsys):
    payload = {"resolved": [RESOLVED], "needs_estimation": [MISSING]}
    code, posted, est = run([{}], payload, estimate=dict(ESTIMATE))
    assert code == 0
    est.assert_called_once_with("peri peri sauce, 60 g", "")
    meal = posted[1]
    assert meal["source"] == "ai_estimate"
    assert meal["display_name"] == "peri peri sauce"
    assert meal["kcal"] == 150.0 and meal["fat_g"] == 12.0
    assert "serving_type" not in meal and "confidence" not in meal
    assert "AI estimate (low confidence)" in meal["notes"]
    result = stdout(capsys)
    estimated = [m for m in result["logged"] if m.get("estimated")]
    assert [m["name"] for m in estimated] == ["peri peri sauce"]
    assert estimated[0]["confidence"] == "low"
    assert "not_found" not in result


def test_matched_items_never_call_the_estimator(capsys):
    code, posted, est = run([{}], {"resolved": [RESOLVED], "needs_estimation": []})
    assert code == 0
    est.assert_not_called()
    assert [p["source"] for p in posted] == ["food"]


def test_estimator_failure_is_reported_and_exits_3_but_keeps_other_items(capsys):
    payload = {"resolved": [RESOLVED], "needs_estimation": [MISSING]}
    code, posted, _ = run(
        [{}], payload, estimate_error=ai_estimate.EstimateError("boom")
    )
    assert code == nutri_cli.EXIT_AI_FAILURE
    result = stdout(capsys)
    assert [m["name"] for m in result["logged"]] == ["Oats"]
    assert result["estimation_failures"][0]["name"] == "peri peri sauce"
    assert "boom" in result["estimation_failures"][0]["reason"]
    assert [p["source"] for p in posted] == ["food"]


def test_person_is_forwarded_on_estimated_meals(capsys):
    payload = {"resolved": [], "needs_estimation": [MISSING]}
    _, posted, _ = run(
        [{}], payload, estimate=dict(ESTIMATE), extra=("--person", "Henry")
    )
    assert posted[0]["person"] == "Henry"
