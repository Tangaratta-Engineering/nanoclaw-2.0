"""target set: --fibre, and omitted fields keep their current value."""

import sys
from pathlib import Path
from unittest.mock import patch

import httpx

sys.path.insert(0, str(Path(__file__).parent))

import nutri_cli


def run(argv, active):
    calls = []

    def api(method, path, json_data=None, params=None):
        calls.append((method, path, json_data, params))
        if method == "GET":
            if isinstance(active, Exception):
                raise active
            return active
        return {"id": 1}

    with patch.object(sys, "argv", ["nutri_cli.py", *argv]), patch.object(
        nutri_cli, "api_call", side_effect=api
    ):
        code = 0
        try:
            nutri_cli.main()
        except SystemExit as e:
            code = e.code
    return code, calls


def post_body(calls):
    return next(c[2] for c in calls if c[0] == "POST")


def test_fibre_only_keeps_existing_kcal_and_protein():
    active = {
        "kcal_target": 2200,
        "protein_g_target": 150,
        "fat_g_target": None,
        "fibre_g_target": None,
    }
    code, calls = run(["target", "set", "--fibre", "30"], active)
    assert code == 0
    assert post_body(calls) == {
        "kcal_target": 2200.0,
        "protein_g_target": 150.0,
        "fibre_g_target": 30.0,
    }


def test_all_three_at_once():
    code, calls = run(
        ["target", "set", "--kcal", "2000", "--protein", "140", "--fibre", "28"], {}
    )
    assert code == 0
    assert post_body(calls) == {
        "kcal_target": 2000.0,
        "protein_g_target": 140.0,
        "fibre_g_target": 28.0,
    }


def test_new_value_overrides_old_and_others_are_kept():
    active = {"kcal_target": 2200, "protein_g_target": 150, "fibre_g_target": 25}
    _, calls = run(["target", "set", "--protein", "160"], active)
    assert post_body(calls) == {
        "kcal_target": 2200.0,
        "protein_g_target": 160.0,
        "fibre_g_target": 25.0,
    }


def test_first_ever_target_needs_kcal():
    not_found = httpx.HTTPStatusError(
        "404", request=httpx.Request("GET", "http://x"), response=httpx.Response(404)
    )
    code, calls = run(["target", "set", "--fibre", "30"], not_found)
    assert code != 0
    assert not any(c[0] == "POST" for c in calls)


def test_first_ever_target_with_kcal_works_when_no_active_target():
    not_found = httpx.HTTPStatusError(
        "404", request=httpx.Request("GET", "http://x"), response=httpx.Response(404)
    )
    code, calls = run(["target", "set", "--kcal", "2000", "--fibre", "30"], not_found)
    assert code == 0
    assert post_body(calls) == {"kcal_target": 2000.0, "fibre_g_target": 30.0}
