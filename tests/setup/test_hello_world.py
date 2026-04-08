from __future__ import annotations

from pathlib import Path

import pytest

from setup import hello_world


@pytest.mark.parametrize(
    ("user_choice", "gantry_key", "expected_bounds"),
    [
        ("1", "CUB_XL", (400.0, 300.0, 80.0)),
        ("2", "CUB", (300.0, 200.0, 80.0)),
    ],
)
def test_select_gantry_loads_renamed_config_files(
    monkeypatch: pytest.MonkeyPatch,
    user_choice: str,
    gantry_key: str,
    expected_bounds: tuple[float, float, float],
) -> None:
    monkeypatch.setattr("builtins.input", lambda _: user_choice)

    gantry_entry, config = hello_world.select_gantry()

    assert gantry_entry == hello_world.GANTRIES[gantry_key]
    assert Path(gantry_entry["config_file"]).is_file()
    assert config["working_volume"]["x_max"] == expected_bounds[0]
    assert config["working_volume"]["y_max"] == expected_bounds[1]
    assert config["working_volume"]["z_max"] == expected_bounds[2]
