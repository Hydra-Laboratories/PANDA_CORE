from test_scripts.overreach_validation_common import (
    MachineBounds,
    iter_scenarios,
    overreach_target,
    safe_interior_target,
)


def _bounds() -> MachineBounds:
    return MachineBounds(
        x_min=-415.0,
        x_max=0.0,
        y_min=-300.0,
        y_max=0.0,
        z_min=-200.0,
        z_max=0.0,
    )


def test_iter_scenarios_default_order():
    assert tuple(iter_scenarios()) == ("x_right", "x_left", "y_up", "y_down")


def test_overreach_target_x_right_goes_past_x_max():
    bounds = _bounds()
    target = overreach_target("x_right", (0.0, -5.0, -2.0), bounds, 1.0)
    assert target == (1.0, -5.0, -2.0)


def test_overreach_target_y_down_goes_past_y_min():
    bounds = _bounds()
    target = overreach_target("y_down", (-10.0, -50.0, -2.0), bounds, 1.0)
    assert target == (-10.0, -301.0, -2.0)


def test_safe_interior_target_x_right_moves_negative():
    bounds = _bounds()
    safe = safe_interior_target("x_right", (0.0, -5.0, -2.0), bounds, 2.0)
    assert safe == (-2.0, -5.0, -2.0)


def test_safe_interior_target_y_down_moves_positive():
    bounds = _bounds()
    safe = safe_interior_target("y_down", (-10.0, -300.0, -2.0), bounds, 2.0)
    assert safe == (-10.0, -298.0, -2.0)
