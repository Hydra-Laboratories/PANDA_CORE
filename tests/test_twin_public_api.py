from board import BoardYamlSchema, load_board_from_yaml_safe
from deck import (
    DeckYamlSchema,
    load_deck_from_yaml_safe,
    load_deck_render_schema,
    load_deck_yaml_with_definitions,
    resolve_definition_asset_path,
)
from gantry import load_gantry_from_yaml_safe, plan_safe_move_segments
from protocol_engine import load_protocol_from_yaml_safe
from validation import validate_deck_positions, validate_gantry_positions


def test_public_api_surface_for_digital_twin_exists():
    assert callable(load_gantry_from_yaml_safe)
    assert callable(load_deck_from_yaml_safe)
    assert callable(load_board_from_yaml_safe)
    assert callable(load_protocol_from_yaml_safe)
    assert callable(validate_deck_positions)
    assert callable(validate_gantry_positions)
    assert callable(plan_safe_move_segments)
    assert callable(load_deck_yaml_with_definitions)
    assert callable(load_deck_render_schema)
    assert callable(resolve_definition_asset_path)
    assert DeckYamlSchema is not None
    assert BoardYamlSchema is not None
