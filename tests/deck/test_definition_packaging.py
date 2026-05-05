"""Confirm the deck labware definition data files ship in the wheel/sdist.

Without this, `pip install`'d copies of cubos can't resolve `load_name:` in
deck YAMLs because `registry.yaml` and the per-definition config YAMLs are
missing from site-packages — they live alongside Python modules but aren't
themselves Python files, so they only get shipped when listed in
`tool.setuptools.package-data` (mirrors `tests/instruments/test_registry_packaging.py`).
"""

import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path


def _copy_repository(source_root: Path, destination_root: Path) -> None:
    shutil.copytree(
        source_root,
        destination_root,
        ignore=shutil.ignore_patterns(
            ".git", ".pytest_cache", "__pycache__", "*.pyc", "*.egg-info",
            "build", "dist", ".venv", "venv",
        ),
    )


def _build_distribution_artifacts(project_root: Path, dist_dir: Path) -> None:
    build_script = (
        "from pathlib import Path; "
        "import os, sys; "
        "import setuptools.build_meta as build_meta; "
        "project_root = Path(sys.argv[1]); "
        "dist_dir = Path(sys.argv[2]); "
        "os.chdir(project_root); "
        "build_meta.build_wheel(str(dist_dir)); "
        "build_meta.build_sdist(str(dist_dir))"
    )
    subprocess.run(
        [sys.executable, "-c", build_script, str(project_root), str(dist_dir)],
        check=True,
    )


def test_wheel_includes_deck_definition_yamls(tmp_path):
    """Each definition needed to resolve a `load_name:` must ship as data.

    Asserts the shipping artifact contains `registry.yaml` plus at least one
    per-definition config — `SBS96WellPlate.yaml` is the canary because it's
    what ASMI deck YAMLs reference.
    """
    repo_root = Path(__file__).resolve().parents[2]
    project_root = tmp_path / "project"
    dist_dir = tmp_path / "dist"

    _copy_repository(repo_root, project_root)
    dist_dir.mkdir()
    _build_distribution_artifacts(project_root, dist_dir)

    wheel_path = next(dist_dir.glob("*.whl"))
    with zipfile.ZipFile(wheel_path) as wheel_file:
        wheel_members = wheel_file.namelist()
    assert "deck/labware/definitions/registry.yaml" in wheel_members
    assert (
        "deck/labware/definitions/sbs_96_wellplate/SBS96WellPlate.yaml"
        in wheel_members
    )

    sdist_path = next(dist_dir.glob("*.tar.gz"))
    with tarfile.open(sdist_path) as sdist_file:
        sdist_members = sdist_file.getnames()
    assert any(
        p.endswith("/src/deck/labware/definitions/registry.yaml")
        for p in sdist_members
    )
    assert any(
        p.endswith(
            "/src/deck/labware/definitions/sbs_96_wellplate/SBS96WellPlate.yaml"
        )
        for p in sdist_members
    )
