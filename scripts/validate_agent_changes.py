#!/usr/bin/env python3
"""Pre-commit validation for multi-agent development.

Maps changed files to affected test suites and runs only those.
Blocks the commit if any affected tests fail.

Usage:
    python scripts/validate_agent_changes.py          # Check staged changes
    python scripts/validate_agent_changes.py --all     # Run all tests
"""

import subprocess
import sys

MODULE_TEST_MAP = {
    "src/gantry/": "pytest tests/gantry/ -v",
    "src/deck/": "pytest tests/test_deck.py tests/test_deck_loader.py tests/test_labware.py -v",
    "src/instruments/": "pytest tests/instruments/ tests/test_uvvis_ccs.py -v",
    "src/board/": "pytest tests/board/ -v",
    "src/protocol_engine/": "pytest tests/protocol_engine/ -v",
    "src/validation/": "pytest tests/validation/ -v",
    "data/": "pytest tests/data/ -v",
}

CONTRACT_TEST = "pytest tests/test_contracts.py -v"
SETUP_TEST = "pytest tests/setup/ -v"


def get_changed_files():
    """Get files staged for commit."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True,
    )
    files = result.stdout.strip().split("\n")
    return [f for f in files if f]


def get_affected_tests(changed_files):
    """Map changed files to the test suites that need to run."""
    commands = set()
    for filepath in changed_files:
        for module_path, test_cmd in MODULE_TEST_MAP.items():
            if filepath.startswith(module_path):
                commands.add(test_cmd)
        if "contracts.py" in filepath:
            commands.add(CONTRACT_TEST)
        if filepath.startswith("tests/setup/") or filepath.startswith("setup/"):
            commands.add(SETUP_TEST)
    return sorted(commands)


def run_tests(test_commands):
    """Run each test command. Return True if all pass."""
    all_passed = True
    for cmd in test_commands:
        print(f"\n  Running: {cmd}")
        result = subprocess.run(
            cmd.split(), capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"  FAILED: {cmd}")
            print(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
            if result.stderr:
                print(result.stderr[-1000:] if len(result.stderr) > 1000 else result.stderr)
            all_passed = False
        else:
            lines = result.stdout.strip().split("\n")
            summary = lines[-1] if lines else "passed"
            print(f"  OK: {summary}")
    return all_passed


def check_backlog_reminder(changed_files):
    """Remind agent to update BACKLOG.md if source files changed."""
    source_changed = any(
        f.startswith("src/") or f.startswith("data/")
        for f in changed_files
    )
    backlog_updated = "BACKLOG.md" in changed_files
    if source_changed and not backlog_updated:
        print("\n  REMINDER: Source files changed but BACKLOG.md was not updated.")
        print("  Consider updating BACKLOG.md with your changes.")


def main():
    if "--all" in sys.argv:
        print("Running ALL tests...")
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/", "-v"],
            capture_output=True, text=True,
        )
        print(result.stdout[-3000:] if len(result.stdout) > 3000 else result.stdout)
        return result.returncode

    changed = get_changed_files()
    if not changed or changed == [""]:
        print("No staged changes found.")
        return 0

    print(f"Staged files ({len(changed)}):")
    for f in changed:
        print(f"  {f}")

    test_commands = get_affected_tests(changed)
    if not test_commands:
        print("\nNo module tests affected by these changes.")
        check_backlog_reminder(changed)
        return 0

    print(f"\nRunning {len(test_commands)} affected test suite(s)...")
    passed = run_tests(test_commands)
    check_backlog_reminder(changed)

    if not passed:
        print("\nCOMMIT BLOCKED: Fix failing tests before committing.")
        return 1

    print("\nAll affected tests passed. Safe to commit.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
