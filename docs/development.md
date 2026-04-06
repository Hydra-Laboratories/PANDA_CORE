# Development

This page covers testing, docs authoring, and the minimum expected workflow for code changes.

## Test Commands

Run the full test suite:

```bash
pytest tests/ -v
```

Target a subsystem:

```bash
pytest tests/protocol_engine -v
pytest tests/gantry -v
pytest tests/data -v
```

## Documentation Workflow

Serve the docs locally:

```bash
mkdocs serve
```

Build the static site:

```bash
mkdocs build
```

The API reference pages under `docs/reference/` are generated at build time from the Python package tree. Do not manually edit generated reference pages.

## Where To Improve Docs

The generated API reference is only as good as the underlying module, class, and function docstrings. The fastest improvements usually come from:

- adding concise module docstrings
- documenting constructor arguments and return values
- documenting YAML expectations near loader and schema code
- documenting command side effects in protocol command handlers

## Suggested Contributor Expectations

- keep diffs small and reviewable
- add or update tests for behavior changes
- run the affected tests before merging
- update narrative docs when the operator workflow changes

## TODO(manual)

- Add local coding standards beyond what the repository already enforces
- Document release/versioning expectations for lab deployments
- Record how hardware-dependent changes are validated before merge
