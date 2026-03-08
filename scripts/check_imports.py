#!/usr/bin/env python3
"""Import boundary checker for PANDA_CORE.

Scans Python files in src/ and verifies that imports respect the
declared dependency graph. Flags violations where a module imports
from a module it shouldn't depend on.

Usage:
    python scripts/check_imports.py
"""

import re
import sys
from pathlib import Path

# Declared dependency graph (from system_manifest.yaml).
# Key = module, Value = set of modules it's allowed to import from.
ALLOWED_DEPENDENCIES = {
    "gantry": set(),
    "deck": set(),
    "instruments": set(),
    "board": {"gantry", "instruments"},
    "protocol_engine": {"board", "deck", "gantry", "instruments", "validation"},
    "validation": {"gantry", "deck", "board", "instruments"},
    "data": {"instruments", "deck"},
}

# Modules that live under src/
SRC_MODULES = {"gantry", "deck", "instruments", "board", "protocol_engine", "validation"}

# data/ is at the repo root, not under src/
ROOT_MODULES = {"data"}

IMPORT_PATTERN = re.compile(
    r"^(?:from\s+(?:src\.)?(\w+)[\.\s]|import\s+(?:src\.)?(\w+))",
)


def get_module_for_file(filepath: Path) -> str | None:
    """Determine which module a file belongs to."""
    parts = filepath.parts
    if "src" in parts:
        idx = parts.index("src")
        if idx + 1 < len(parts):
            return parts[idx + 1]
    if "data" in parts:
        return "data"
    return None


def check_file(filepath: Path) -> list[str]:
    """Check a single file for import boundary violations."""
    violations = []
    module = get_module_for_file(filepath)
    if module is None or module not in ALLOWED_DEPENDENCIES:
        return violations

    allowed = ALLOWED_DEPENDENCIES[module] | {module}

    with open(filepath) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line.startswith(("from ", "import ")):
                continue
            match = IMPORT_PATTERN.match(line)
            if not match:
                continue
            imported_module = match.group(1) or match.group(2)
            if imported_module in (SRC_MODULES | ROOT_MODULES) and imported_module not in allowed:
                violations.append(
                    f"  {filepath}:{line_num}: '{module}' imports from "
                    f"'{imported_module}' (not in allowed dependencies)"
                )
    return violations


def main():
    src_dir = Path("src")
    data_dir = Path("data")

    all_violations = []

    for directory in [src_dir, data_dir]:
        if not directory.exists():
            continue
        for py_file in directory.rglob("*.py"):
            violations = check_file(py_file)
            all_violations.extend(violations)

    if all_violations:
        print(f"Found {len(all_violations)} import boundary violation(s):\n")
        for v in all_violations:
            print(v)
        print(
            "\nUpdate ALLOWED_DEPENDENCIES in this script or "
            "system_manifest.yaml if the dependency is intentional."
        )
        return 1

    print("All imports respect module boundaries.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
