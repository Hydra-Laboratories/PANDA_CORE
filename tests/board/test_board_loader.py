import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from board.errors import BoardLoaderError
from board.loader import load_board_from_yaml, load_board_from_yaml_safe
from board.yaml_schema import BoardYamlSchema, InstrumentYamlEntry
from instruments.asmi.driver import ASMI
from instruments.filmetrics.driver import Filmetrics
from instruments.pipette.driver import Pipette
from instruments.uvvis_ccs.driver import UVVisCCS
from board import Board


def _mock_gantry():
    gantry = MagicMock()
    gantry.get_coordinates.return_value = {"x": 0.0, "y": 0.0, "z": 0.0}
    return gantry


def _write_yaml(tmp_path: Path, content: str) -> Path:
    """Write YAML text to a temp file and return the path."""
    path = tmp_path / "board.yaml"
    path.write_text(textwrap.dedent(content))
    return path


# --- Schema tests ------------------------------------------------------------


class TestInstrumentYamlEntry:

    def test_allows_extra_fields(self):
        entry = InstrumentYamlEntry(
            type="uvvis_ccs",
            offset_x=1.0,
            serial_number="ABC123",
        )
        assert entry.type == "uvvis_ccs"
        assert entry.model_extra["serial_number"] == "ABC123"

    def test_defaults_for_optional_fields(self):
        entry = InstrumentYamlEntry(type="uvvis_ccs")
        assert entry.offset_x == 0.0
        assert entry.offset_y == 0.0
        assert entry.depth == 0.0
        assert entry.measurement_height == 0.0


class TestBoardYamlSchema:

    def test_forbids_extra_root_keys(self):
        with pytest.raises(Exception):
            BoardYamlSchema.model_validate({
                "instruments": {"a": {"type": "uvvis_ccs"}},
                "labware": {},
            })

    def test_requires_instruments_key(self):
        with pytest.raises(Exception):
            BoardYamlSchema.model_validate({})


# --- Loader: valid YAML ------------------------------------------------------


class TestLoadBoardSingleInstrument:

    def test_loads_single_uvvis(self, tmp_path):
        yaml_path = _write_yaml(tmp_path, """\
            instruments:
              uvvis:
                type: uvvis_ccs
                offset_x: -15.0
                offset_y: 0.0
                depth: -5.0
                measurement_height: 3.0
        """)
        board = load_board_from_yaml(yaml_path, _mock_gantry())

        assert isinstance(board, Board)
        assert "uvvis" in board.instruments
        instr = board.instruments["uvvis"]
        assert isinstance(instr, UVVisCCS)
        assert instr.offset_x == -15.0
        assert instr.offset_y == 0.0
        assert instr.depth == -5.0
        assert instr.measurement_height == 3.0


class TestLoadBoardMultipleInstruments:

    def test_loads_two_instruments(self, tmp_path):
        yaml_path = _write_yaml(tmp_path, """\
            instruments:
              uvvis:
                type: uvvis_ccs
                offset_x: -15.0
              pipette:
                type: pipette
                offset_x: -10.0
                offset_y: 5.0
                depth: -2.0
        """)
        board = load_board_from_yaml(yaml_path, _mock_gantry())

        assert len(board.instruments) == 2
        assert isinstance(board.instruments["uvvis"], UVVisCCS)
        assert isinstance(board.instruments["pipette"], Pipette)
        assert board.instruments["pipette"].offset_x == -10.0

    def test_loads_filmetrics(self, tmp_path):
        yaml_path = _write_yaml(tmp_path, """\
            instruments:
              film:
                type: filmetrics
                offset_x: -20.0
                measurement_height: 1.5
        """)
        board = load_board_from_yaml(yaml_path, _mock_gantry())

        instr = board.instruments["film"]
        assert isinstance(instr, Filmetrics)
        assert instr.measurement_height == 1.5


class TestLoadBoardMeasurementHeight:

    def test_measurement_height_passes_through(self, tmp_path):
        yaml_path = _write_yaml(tmp_path, """\
            instruments:
              sensor:
                type: uvvis_ccs
                measurement_height: 4.5
        """)
        board = load_board_from_yaml(yaml_path, _mock_gantry())
        assert board.instruments["sensor"].measurement_height == 4.5

    def test_measurement_height_defaults_to_zero(self, tmp_path):
        yaml_path = _write_yaml(tmp_path, """\
            instruments:
              sensor:
                type: uvvis_ccs
        """)
        board = load_board_from_yaml(yaml_path, _mock_gantry())
        assert board.instruments["sensor"].measurement_height == 0.0


class TestLoadBoardGantry:

    def test_gantry_attached_to_board(self, tmp_path):
        yaml_path = _write_yaml(tmp_path, """\
            instruments:
              uvvis:
                type: uvvis_ccs
        """)
        gantry = _mock_gantry()
        board = load_board_from_yaml(yaml_path, gantry)
        assert board.gantry is gantry


# --- Loader: error cases -----------------------------------------------------


class TestLoadBoardUnknownType:

    def test_unknown_type_raises_key_error(self, tmp_path):
        yaml_path = _write_yaml(tmp_path, """\
            instruments:
              mystery:
                type: does_not_exist
        """)
        with pytest.raises(KeyError):
            load_board_from_yaml(yaml_path, _mock_gantry())


class TestLoadBoardMissingField:

    def test_missing_type_raises_validation_error(self, tmp_path):
        yaml_path = _write_yaml(tmp_path, """\
            instruments:
              sensor:
                offset_x: 1.0
        """)
        with pytest.raises(Exception):
            load_board_from_yaml(yaml_path, _mock_gantry())


class TestLoadBoardExtraRootKey:

    def test_extra_root_key_rejected(self, tmp_path):
        yaml_path = _write_yaml(tmp_path, """\
            instruments:
              uvvis:
                type: uvvis_ccs
            labware:
              plate: {}
        """)
        with pytest.raises(Exception):
            load_board_from_yaml(yaml_path, _mock_gantry())


class TestLoadBoardFileNotFound:

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_board_from_yaml("/nonexistent/board.yaml", _mock_gantry())


# --- Safe loader --------------------------------------------------------------


class TestLoadBoardFromYamlSafe:

    def test_returns_board_on_valid_yaml(self, tmp_path):
        yaml_path = _write_yaml(tmp_path, """\
            instruments:
              uvvis:
                type: uvvis_ccs
        """)
        board = load_board_from_yaml_safe(yaml_path, _mock_gantry())
        assert isinstance(board, Board)
        assert "uvvis" in board.instruments

    def test_wraps_unknown_type_in_board_loader_error(self, tmp_path):
        yaml_path = _write_yaml(tmp_path, """\
            instruments:
              mystery:
                type: does_not_exist
        """)
        with pytest.raises(BoardLoaderError, match="Unknown instrument type"):
            load_board_from_yaml_safe(yaml_path, _mock_gantry())

    def test_wraps_validation_error_in_board_loader_error(self, tmp_path):
        yaml_path = _write_yaml(tmp_path, """\
            instruments:
              sensor:
                offset_x: 1.0
        """)
        with pytest.raises(BoardLoaderError, match="Board YAML error"):
            load_board_from_yaml_safe(yaml_path, _mock_gantry())

    def test_wraps_extra_root_key_in_board_loader_error(self, tmp_path):
        yaml_path = _write_yaml(tmp_path, """\
            instruments:
              uvvis:
                type: uvvis_ccs
            extra_key: bad
        """)
        with pytest.raises(BoardLoaderError, match="Board YAML error"):
            load_board_from_yaml_safe(yaml_path, _mock_gantry())

    def test_wraps_file_not_found_in_board_loader_error(self):
        with pytest.raises(BoardLoaderError, match="Board loader error"):
            load_board_from_yaml_safe("/nonexistent/board.yaml", _mock_gantry())

    def test_wraps_invalid_yaml_in_board_loader_error(self, tmp_path):
        path = tmp_path / "bad.yaml"
        path.write_text("instruments:\n  - [invalid: yaml: :\n")
        with pytest.raises(BoardLoaderError, match="Board YAML"):
            load_board_from_yaml_safe(path, _mock_gantry())


# --- Mock mode ---------------------------------------------------------------


class TestLoadBoardMockMode:

    def test_mock_mode_creates_offline_instrument(self, tmp_path):
        yaml_path = _write_yaml(tmp_path, """\
            instruments:
              pip:
                type: pipette
                offset_x: -10.0
        """)
        board = load_board_from_yaml(yaml_path, _mock_gantry(), mock_mode=True)
        assert isinstance(board.instruments["pip"], Pipette)
        assert board.instruments["pip"]._offline is True

    def test_mock_mode_false_keeps_online(self, tmp_path):
        yaml_path = _write_yaml(tmp_path, """\
            instruments:
              uvvis:
                type: uvvis_ccs
        """)
        board = load_board_from_yaml(yaml_path, _mock_gantry(), mock_mode=False)
        assert isinstance(board.instruments["uvvis"], UVVisCCS)
        assert board.instruments["uvvis"]._offline is False

    def test_mock_mode_swaps_all_instruments(self, tmp_path):
        yaml_path = _write_yaml(tmp_path, """\
            instruments:
              pip:
                type: pipette
              uvvis:
                type: uvvis_ccs
              film:
                type: filmetrics
        """)
        board = load_board_from_yaml(yaml_path, _mock_gantry(), mock_mode=True)
        assert isinstance(board.instruments["pip"], Pipette) and board.instruments["pip"]._offline is True
        assert isinstance(board.instruments["uvvis"], UVVisCCS) and board.instruments["uvvis"]._offline is True
        assert isinstance(board.instruments["film"], Filmetrics) and board.instruments["film"]._offline is True

    def test_mock_mode_safe_loader_passes_through(self, tmp_path):
        yaml_path = _write_yaml(tmp_path, """\
            instruments:
              pip:
                type: pipette
        """)
        board = load_board_from_yaml_safe(yaml_path, _mock_gantry(), mock_mode=True)
        assert isinstance(board.instruments["pip"], Pipette)
        assert board.instruments["pip"]._offline is True

    def test_mock_mode_sets_offline_for_asmi(self, tmp_path):
        """ASMI supports offline=True -- mock_mode should set the flag, not swap class."""
        yaml_path = _write_yaml(tmp_path, """\
            instruments:
              asmi:
                type: asmi
                force_threshold: -100
        """)
        board = load_board_from_yaml(yaml_path, _mock_gantry(), mock_mode=True)
        instr = board.instruments["asmi"]
        assert isinstance(instr, ASMI)
        assert instr._offline is True

    def test_no_mock_mode_asmi_stays_online(self, tmp_path):
        yaml_path = _write_yaml(tmp_path, """\
            instruments:
              asmi:
                type: asmi
        """)
        board = load_board_from_yaml(yaml_path, _mock_gantry(), mock_mode=False)
        instr = board.instruments["asmi"]
        assert isinstance(instr, ASMI)
        assert instr._offline is False
