"""edit: --fibre support, and 0 is a real value rather than 'not given'."""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

import nutri_cli


def run(argv):
    with patch.object(sys, "argv", ["nutri_cli.py", *argv]), patch.object(
        nutri_cli, "api_call", return_value={"id": 58}
    ) as api:
        code = 0
        try:
            nutri_cli.main()
        except SystemExit as e:
            code = e.code
    return code, api


def test_edit_fibre_alongside_other_macros():
    code, api = run(["edit", "58", "--kcal", "29", "--fibre", "2.7"])
    assert code == 0
    api.assert_called_once_with("PATCH", "/meals/58", {"kcal": 29.0, "fibre_g": 2.7})


def test_edit_fibre_only_sends_only_fibre():
    _, api = run(["edit", "58", "--fibre", "2.7"])
    assert api.call_args.args[2] == {"fibre_g": 2.7}


def test_zero_is_a_value_not_skipped():
    _, api = run(["edit", "58", "--fibre", "0", "--kcal", "0"])
    assert api.call_args.args[2] == {"kcal": 0.0, "fibre_g": 0.0}


def test_all_macro_fields_map_to_api_names():
    _, api = run(
        [
            "edit",
            "58",
            "--protein",
            "1",
            "--fat",
            "2",
            "--carbs",
            "3",
            "--servings",
            "2",
        ]
    )
    assert api.call_args.args[2] == {
        "servings": 2.0,
        "protein_g": 1.0,
        "fat_g": 2.0,
        "carbs_g": 3.0,
    }


def test_edit_with_nothing_to_change_is_an_error_and_makes_no_call():
    code, api = run(["edit", "58"])
    assert code != 0
    api.assert_not_called()
