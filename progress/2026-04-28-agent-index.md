# 2026-04-28 Agent index docs

## Work done

- Added `docs/agent-index.md` as a compact retrieval map for CubOS coding agents.
- Added a short `AGENTS.md` section pointing agents to the retrieval index before coding.
- Added a `CLAUDE.md` retrieval rule so Claude-style agents read the same index.

## Why

The Vercel AGENTS.md eval writeup suggests always-loaded project context and compact doc indexes are more reliable than optional skill invocation for general framework/project knowledge. CubOS has hardware and validation semantics that should be retrieved from source/docs rather than guessed from model memory.

## Verification

Docs-only change. Verified by direct inspection and repository grep for the new routing section.

## Hardware impact

No hardware behavior changed. No physical hardware validation required.
