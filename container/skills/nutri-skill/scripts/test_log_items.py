"""`log` food form: one call to POST /meals/log-items; the API decides the source."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import nutri_cli


def _logged(name="meat pie", tier="open_food_facts"):
    return {
        "name": name,
        "quantity": 1,
        "unit": "item",
        "status": "logged",
        "source_tier": tier,
        "meal_id": 5,
        "kcal": 320.0,
        "error": None,
    }


def _failed(code="AI_NO_RESULT", name="mystery"):
    return {
        "name": name,
        "quantity": 1,
        "unit": "item",
        "status": "failed",
        "source_tier": None,
        "meal_id": None,
        "error": {"error": "AIEstimateError", "detail": "no idea", "code": code},
    }


def _result(*items):
    logged = sum(1 for i in items if i["status"] == "logged")
    return {
        "meal_category": "lunch",
        "person": "George",
        "logged_count": logged,
        "failed_count": len(items) - logged,
        "items": list(items),
    }


def run(argv, api_return=None, api_side_effect=None):
    with patch.object(sys, "argv", ["nutri_cli.py", *argv]), patch.object(
        nutri_cli, "api_call", return_value=api_return, side_effect=api_side_effect
    ) as api:
        code = 0
        try:
            nutri_cli.main()
        except SystemExit as e:
            code = e.code
    return code, api


def test_single_item(capsys):
    res = _result(_logged())
    code, api = run(
        [
            "log",
            "--meal",
            "lunch",
            "--name",
            "meat pie",
            "--quantity",
            "1",
            "--unit",
            "item",
        ],
        res,
    )
    assert code == 0
    api.assert_called_once_with(
        "POST",
        "/meals/log-items",
        {
            "meal_category": "lunch",
            "items": [{"name": "meat pie", "quantity": 1.0, "unit": "item"}],
        },
    )
    assert json.loads(capsys.readouterr().out) == res


def test_repeated_item_flags_and_pipe_in_name(capsys):
    res = _result(_logged(), _logged("cola"))
    code, api = run(
        [
            "log",
            "--meal",
            "lunch",
            "--item",
            "meat pie|1|item",
            "--item",
            "mac|n|cheese|250|g",
        ],
        res,
    )
    # "mac|n|cheese" keeps its pipes because only the last two fields are split off
    assert code == 0
    items = api.call_args.args[2]["items"]
    assert items == [
        {"name": "meat pie", "quantity": 1.0, "unit": "item"},
        {"name": "mac|n|cheese", "quantity": 250.0, "unit": "g"},
    ]


def test_items_json_and_item_combine(capsys):
    res = _result(_logged(), _logged("cola"))
    code, api = run(
        [
            "log",
            "--meal",
            "snack",
            "--item",
            "apple|1|item",
            "--items-json",
            '[{"name":"cola","quantity":375,"unit":"ML"}]',
        ],
        res,
    )
    assert code == 0
    assert [i["name"] for i in api.call_args.args[2]["items"]] == ["apple", "cola"]
    assert api.call_args.args[2]["items"][1]["unit"] == "ml"


def test_json_printed_unchanged_on_partial_failure_exit_3(capsys):
    res = _result(_logged(), _failed("AI_NO_RESULT"))
    code, _ = run(
        [
            "log",
            "--meal",
            "lunch",
            "--item",
            "meat pie|1|item",
            "--item",
            "mystery|1|item",
        ],
        res,
    )
    assert code == nutri_cli.EXIT_AI_FAILURE == 3
    assert json.loads(capsys.readouterr().out) == res


def test_ai_estimate_failed_exit_3(capsys):
    code, _ = run(
        ["log", "--meal", "lunch", "--name", "x", "--quantity", "1", "--unit", "item"],
        _result(_failed("AI_ESTIMATE_FAILED")),
    )
    assert code == 3


def test_internal_error_item_exit_1_but_json_printed(capsys):
    res = _result(_failed("INTERNAL_ERROR"))
    code, _ = run(
        ["log", "--meal", "lunch", "--name", "x", "--quantity", "1", "--unit", "item"],
        res,
    )
    assert code == nutri_cli.EXIT_ERROR == 1
    assert json.loads(capsys.readouterr().out) == res


def test_ai_failure_wins_over_internal_error(capsys):
    code, _ = run(
        ["log", "--meal", "lunch", "--item", "a|1|item", "--item", "b|1|item"],
        _result(_failed("INTERNAL_ERROR"), _failed("AI_NO_RESULT")),
    )
    assert code == 3


def test_network_or_5xx_error_exit_1(capsys):
    code, _ = run(
        ["log", "--meal", "lunch", "--name", "x", "--quantity", "1", "--unit", "item"],
        api_side_effect=RuntimeError("boom"),
    )
    assert code == 1
    assert json.loads(capsys.readouterr().err)["code"] == "LOG_ERROR"


def test_person_passthrough_before_and_after(capsys):
    res = _result(_logged())
    for argv in (
        ["--person", "Henry", "log", "--meal", "lunch", "--item", "pie|1|item"],
        ["log", "--meal", "lunch", "--item", "pie|1|item", "--person", "Henry"],
    ):
        _, api = run(argv, res)
        assert api.call_args.args[2]["person"] == "Henry"


def test_person_not_found_exits_2(capsys):
    import httpx

    resp = httpx.Response(
        404,
        json={
            "detail": "Unknown person 'Bob'",
            "code": "PERSON_NOT_FOUND",
            "known_persons": ["George"],
        },
        request=httpx.Request("POST", "http://x/meals/log-items"),
    )
    from unittest.mock import MagicMock

    client = MagicMock()
    client.__enter__.return_value = client
    client.request.return_value = resp
    argv = [
        "nutri_cli.py",
        "log",
        "--meal",
        "lunch",
        "--item",
        "pie|1|item",
        "--person",
        "Bob",
    ]
    with patch.object(sys, "argv", argv), patch(
        "httpx.Client", return_value=client
    ), pytest.raises(SystemExit) as exc:
        nutri_cli.main()
    assert exc.value.code == 2
    err = json.loads(capsys.readouterr().err)
    assert err["code"] == "PERSON_NOT_FOUND" and err["known_persons"] == ["George"]
    assert client.request.call_args.kwargs["json"]["person"] == "Bob"


@pytest.mark.parametrize(
    "extra",
    [
        [],  # nothing to log
        ["--name", "pie"],  # no quantity/unit
        ["--name", "pie", "--quantity", "0", "--unit", "item"],
        ["--name", "pie", "--quantity", "-1", "--unit", "item"],
        ["--name", "pie", "--quantity", "abc", "--unit", "item"],
        ["--name", "pie", "--quantity", "1", "--unit", "serving"],
        ["--name", " ", "--quantity", "1", "--unit", "item"],
        ["--item", "pie|1"],
        ["--items-json", "not json"],
        ["--items-json", '{"name":"pie"}'],
        ["--items-json", '[{"name":"pie","quantity":1}]'],
        ["--item", "pie|1|item", "--recipe", "Chilli"],
        ["--servings", "2", "--item", "pie|1|item"],
    ],
)
def test_validation_errors_make_no_api_call(capsys, extra):
    code, api = run(["log", "--meal", "lunch", *extra])
    assert code == 1
    api.assert_not_called()
    assert json.loads(capsys.readouterr().err)["code"] == "INVALID_ARGS"


def test_too_many_items_rejected(capsys):
    items = [{"name": f"f{i}", "quantity": 1, "unit": "item"} for i in range(21)]
    code, api = run(["log", "--meal", "lunch", "--items-json", json.dumps(items)])
    assert code == 1
    api.assert_not_called()


def test_recipe_log_still_works(capsys):
    def side(method, path, *a, **k):
        if path == "/recipes":
            return [{"id": 4, "name": "Chilli"}]
        return {"id": 9}

    code, api = run(
        ["log", "--meal", "dinner", "--recipe", "Chilli", "--servings", "1.5"],
        api_side_effect=side,
    )
    assert code == 0
    post = [c for c in api.call_args_list if c.args[1] == "/meals"][0]
    assert post.args[2] == {
        "meal_category": "dinner",
        "source": "recipe",
        "recipe_id": 4,
        "servings": 1.5,
    }


@pytest.mark.parametrize(
    "argv",
    [
        ["log", "--meal", "lunch", "--food", "Oats"],
        ["log", "--meal", "lunch", "--estimate", "a pie"],
        ["resolve-items", "--meal", "lunch", "--items", "[]"],
    ],
)
def test_removed_commands_rejected_by_argparse(argv, capsys):
    code, _ = run(argv)
    assert code == 2


def test_removed_text_estimation_gone():
    import ai_estimate

    assert not hasattr(ai_estimate, "call_text_estimation")
    assert not hasattr(nutri_cli, "cmd_resolve_items")
