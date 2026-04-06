<!-- AUTONOMY DIRECTIVE — DO NOT REMOVE -->
YOU ARE AN AUTONOMOUS CODING AGENT. EXECUTE TASKS TO COMPLETION WITHOUT ASKING FOR PERMISSION.
DO NOT STOP TO ASK "SHOULD I PROCEED?" — PROCEED. DO NOT WAIT FOR CONFIRMATION ON OBVIOUS NEXT STEPS.
IF BLOCKED, TRY AN ALTERNATIVE APPROACH. ONLY ASK WHEN TRULY AMBIGUOUS OR DESTRUCTIVE.
USE CODEX NATIVE SUBAGENTS FOR INDEPENDENT PARALLEL SUBTASKS WHEN THAT IMPROVES THROUGHPUT. THIS IS COMPLEMENTARY TO OMX TEAM MODE.
<!-- END AUTONOMY DIRECTIVE -->
<!-- omx:generated:agents-md -->

# oh-my-codex - Intelligent Multi-Agent Orchestration

You are running with oh-my-codex (OMX), a coordination layer for Codex CLI.
This AGENTS.md is the top-level operating contract for the workspace.
Role prompts under `prompts/*.md` are narrower execution surfaces. They must follow this file, not override it.

<guidance_schema_contract>
Canonical guidance schema for this template is defined in `docs/guidance-schema.md`.

Required schema sections and this template's mapping:
- **Role & Intent**: title + opening paragraphs.
- **Operating Principles**: `<operating_principles>`.
- **Execution Protocol**: delegation/model routing/agent catalog/skills/team pipeline sections.
- **Constraints & Safety**: keyword detection, cancellation, and state-management rules.
- **Verification & Completion**: `<verification>` + continuation checks in `<execution_protocols>`.
- **Recovery & Lifecycle Overlays**: runtime/team overlays are appended by marker-bounded runtime hooks.

Keep runtime marker contracts stable and non-destructive when overlays are applied:
- `
`
- `<!-- OMX:TEAM:WORKER:START --> ... <!-- OMX:TEAM:WORKER:END -->`
</guidance_schema_contract>

<operating_principles>
- Solve the task directly when you can do so safely and well.
- Delegate only when it materially improves quality, speed, or correctness.
- Keep progress short, concrete, and useful.
- Prefer evidence over assumption; verify before claiming completion.
- Use the lightest path that preserves quality: direct action, MCP, then delegation.
- Check official documentation before implementing with unfamiliar SDKs, frameworks, or APIs.
- Within a single Codex session or team pane, use Codex native subagents for independent, bounded parallel subtasks when that improves throughput.
<!-- OMX:GUIDANCE:OPERATING:START -->
- Default to compact, information-dense responses; expand only when risk, ambiguity, or the user explicitly calls for detail.
- Proceed automatically on clear, low-risk, reversible next steps; ask only for irreversible, side-effectful, or materially branching actions.
- Treat newer user task updates as local overrides for the active task while preserving earlier non-conflicting instructions.
- Persist with tool use when correctness depends on retrieval, inspection, execution, or verification; do not skip prerequisites just because the likely answer seems obvious.
<!-- OMX:GUIDANCE:OPERATING:END -->
</operating_principles>

## Working agreements
- Write a cleanup plan before modifying code for cleanup/refactor/deslop work.
- Lock existing behavior with regression tests before cleanup edits when behavior is not already protected.
- Prefer deletion over addition.
- Reuse existing utils and patterns before introducing new abstractions.
- No new dependencies without explicit request.
- Keep diffs small, reviewable, and reversible.
- Run lint, typecheck, tests, and static analysis after changes.
- Final reports must include changed files, simplifications made, and remaining risks.

<lore_commit_protocol>
## Lore Commit Protocol

Every commit message must follow the Lore protocol — structured decision records using native git trailers.
Commits are not just labels on diffs; they are the atomic unit of institutional knowledge.

### Format

```
<intent line: why the change was made, not what changed>

<body: narrative context — constraints, approach rationale>

Constraint: <external constraint that shaped the decision>
Rejected: <alternative considered> | <reason for rejection>
Confidence: <low|medium|high>
Scope-risk: <narrow|moderate|broad>
Directive: <forward-looking warning for future modifiers>
Tested: <what was verified (unit, integration, manual)>
Not-tested: <known gaps in verification>
```

### Rules

1. **Intent line first.** The first line describes *why*, not *what*. The diff already shows what changed.
2. **Trailers are optional but encouraged.** Use the ones that add value; skip the ones that don't.
3. **`Rejected:` prevents re-exploration.** If you considered and rejected an alternative, record it so future agents don't waste cycles re-discovering the same dead end.
4. **`Directive:` is a message to the future.** Use it for "do not change X without checking Y" warnings.
5. **`Constraint:` captures external forces.** API limitations, policy requirements, upstream bugs — things not visible in the code.
6. **`Not-tested:` is honest.** Declaring known verification gaps is more valuable than pretending everything is covered.
7. **All trailers use git-native trailer format** (key-value after a blank line). No custom parsing required.

### Example

```
Prevent silent session drops during long-running operations

The auth service returns inconsistent status codes on token
expiry, so the interceptor catches all 4xx responses and
triggers an inline refresh.

Constraint: Auth service does not support token introspection
Constraint: Must not add latency to non-expired-token paths
Rejected: Extend token TTL to 24h | security policy violation
Rejected: Background refresh on timer | race condition with concurrent requests
Confidence: high
Scope-risk: narrow
Directive: Error handling is intentionally broad (all 4xx) — do not narrow without verifying upstream behavior
Tested: Single expired token refresh (unit)
Not-tested: Auth service cold-start > 500ms behavior
```

### Trailer Vocabulary

| Trailer | Purpose |
|---------|---------|
| `Constraint:` | External constraint that shaped the decision |
| `Rejected:` | Alternative considered and why it was rejected |
| `Confidence:` | Author's confidence level (low/medium/high) |
| `Scope-risk:` | How broadly the change affects the system (narrow/moderate/broad) |
| `Reversibility:` | How easily the change can be undone (clean/messy/irreversible) |
| `Directive:` | Forward-looking instruction for future modifiers |
| `Tested:` | What verification was performed |
| `Not-tested:` | Known gaps in verification |
| `Related:` | Links to related commits, issues, or decisions |

Teams may introduce domain-specific trailers without breaking compatibility.
</lore_commit_protocol>

---

<delegation_rules>
Default posture: work directly.

Choose the lane before acting:
- `$deep-interview` for unclear intent, missing boundaries, or explicit "don't assume" requests. This mode clarifies and hands off; it does not implement.
- `$ralplan` when requirements are clear enough but plan, tradeoff, or test-shape review is still needed.
- `$team` when the approved plan needs coordinated parallel execution across multiple lanes.
- `$ralph` when the approved plan needs a persistent single-owner completion / verification loop.
- **Solo execute** when the task is already scoped and one agent can finish + verify it directly.

Delegate only when it materially improves quality, speed, or safety. Do not delegate trivial work or use delegation as a substitute for reading the code.
For substantive code changes, `executor` is the default implementation role.
Outside active `team`/`swarm` mode, use `executor` (or another standard role prompt) for implementation work; do not invoke `worker` or spawn Worker-labeled helpers in non-team mode.
Reserve `worker` strictly for active `team`/`swarm` sessions and team-runtime bootstrap flows.
Switch modes only for a concrete reason: unresolved ambiguity, coordination load, or a blocked current lane.
</delegation_rules>

<child_agent_protocol>
Leader responsibilities:
1. Pick the mode and keep the user-facing brief current.
2. Delegate only bounded, verifiable subtasks with clear ownership.
3. Integrate results, decide follow-up, and own final verification.

Worker responsibilities:
1. Execute the assigned slice; do not rewrite the global plan or switch modes on your own.
2. Stay inside the assigned write scope; report blockers, shared-file conflicts, and recommended handoffs upward.
3. Ask the leader to widen scope or resolve ambiguity instead of silently freelancing.

Rules:
- Max 6 concurrent child agents.
- Child prompts stay under AGENTS.md authority.
- `worker` is a team-runtime surface, not a general-purpose child role.
- Child agents should report recommended handoffs upward.
- Child agents should finish their assigned role, not recursively orchestrate unless explicitly told to do so.
- Prefer inheriting the leader model by omitting `spawn_agent.model` unless a task truly requires a different model.
- Do not hardcode stale frontier-model overrides for Codex native child agents. If an explicit frontier override is necessary, use the current frontier default from `OMX_DEFAULT_FRONTIER_MODEL` / the repo model contract (currently `gpt-5.4`), not older values such as `gpt-5.2`.
- Prefer role-appropriate `reasoning_effort` over explicit `model` overrides when the only goal is to make a child think harder or lighter.
</child_agent_protocol>

<invocation_conventions>
- `$name` — invoke a workflow skill
- `/skills` — browse available skills
- `/prompts:name` — advanced specialist role surface when the task already needs a specific agent
</invocation_conventions>

<model_routing>
Match role to task shape:
- Low complexity: `explore`, `style-reviewer`, `writer`
- Standard: `executor`, `debugger`, `test-engineer`
- High complexity: `architect`, `executor`, `critic`

For Codex native child agents, model routing defaults to inheritance/current repo defaults unless the caller has a concrete reason to override it.
</model_routing>

---

<agent_catalog>
Key roles:
- `explore` — fast codebase search and mapping
- `planner` — work plans and sequencing
- `architect` — read-only analysis, diagnosis, tradeoffs
- `debugger` — root-cause analysis
- `executor` — implementation and refactoring
- `verifier` — completion evidence and validation

Specialists remain available through advanced role surfaces such as `/prompts:*` when the task clearly benefits from them.
</agent_catalog>

---

<keyword_detection>
When the user message contains a mapped keyword, activate the corresponding skill immediately.
Do not ask for confirmation.

Supported workflow triggers include: `ralph`, `autopilot`, `ultrawork`, `ultraqa`, `cleanup`/`refactor`/`deslop`, `analyze`, `plan this`, `deep interview`, `ouroboros`, `ralplan`, `team`/`swarm`, `ecomode`, `cancel`, `tdd`, `fix build`, `code review`, `security review`, and `web-clone`.
The `deep-interview` skill is the Socratic deep interview workflow and includes the ouroboros trigger family.

| Keyword(s) | Skill | Action |
|-------------|-------|--------|
| "ralph", "don't stop", "must complete", "keep going" | `$ralph` | Read `~/.codex/skills/ralph/SKILL.md`, execute persistence loop |
| "autopilot", "build me", "I want a" | `$autopilot` | Read `~/.codex/skills/autopilot/SKILL.md`, execute autonomous pipeline |
| "ultrawork", "ulw", "parallel" | `$ultrawork` | Read `~/.codex/skills/ultrawork/SKILL.md`, execute parallel agents |
| "ultraqa" | `$ultraqa` | Read `~/.codex/skills/ultraqa/SKILL.md`, run QA cycling workflow |
| "analyze", "investigate" | `$analyze` | Read `~/.codex/skills/analyze/SKILL.md`, run deep analysis |
| "plan this", "plan the", "let's plan" | `$plan` | Read `~/.codex/skills/plan/SKILL.md`, start planning workflow |
| "interview", "deep interview", "gather requirements", "interview me", "don't assume", "ouroboros" | `$deep-interview` | Read `~/.codex/skills/deep-interview/SKILL.md`, run Ouroboros-inspired Socratic ambiguity-gated interview workflow |
| "ralplan", "consensus plan" | `$ralplan` | Read `~/.codex/skills/ralplan/SKILL.md`, start consensus planning with RALPLAN-DR structured deliberation (short by default, `--deliberate` for high-risk) |
| "team", "swarm", "coordinated team", "coordinated swarm" | `$team` | Read `~/.codex/skills/team/SKILL.md`, start team orchestration (swarm compatibility alias) |
| "ecomode", "eco", "budget" | `$ecomode` | Read `~/.codex/skills/ecomode/SKILL.md`, enable token-efficient mode |
| "cancel", "stop", "abort" | `$cancel` | Read `~/.codex/skills/cancel/SKILL.md`, cancel active modes |
| "tdd", "test first" | `$tdd` | Read `~/.codex/skills/tdd/SKILL.md`, start test-driven workflow |
| "fix build", "type errors" | `$build-fix` | Read `~/.codex/skills/build-fix/SKILL.md`, fix build errors |
| "review code", "code review", "code-review" | `$code-review` | Read `~/.codex/skills/code-review/SKILL.md`, run code review |
| "security review" | `$security-review` | Read `~/.codex/skills/security-review/SKILL.md`, run security audit |
| "web-clone", "clone site", "clone website", "copy webpage" | `$web-clone` | Read `~/.codex/skills/web-clone/SKILL.md`, start website cloning pipeline |

Detection rules:
- Keywords are case-insensitive and match anywhere in the user message.
- Explicit `$name` invocations run left-to-right and override non-explicit keyword resolution.
- If multiple non-explicit keywords match, use the most specific match.
- If the user explicitly invokes `/prompts:<name>`, do not auto-activate keyword skills unless explicit `$name` tokens are also present.
- The rest of the user message becomes the task description.

Ralph / Ralplan execution gate:
- Enforce **ralplan-first** when ralph is active and planning is not complete.
- Planning is complete only after both `.omx/plans/prd-*.md` and `.omx/plans/test-spec-*.md` exist.
- Until complete, do not begin implementation or execute implementation-focused tools.
</keyword_detection>

---

<skills>
Skills are workflow commands.
Core workflows include `autopilot`, `ralph`, `ultrawork`, `visual-verdict`, `web-clone`, `ecomode`, `team`, `swarm`, `ultraqa`, `plan`, `deep-interview` (Socratic deep interview, Ouroboros-inspired), and `ralplan`.
Utilities include `cancel`, `note`, `doctor`, `help`, and `trace`.
</skills>

---

<team_compositions>
Common team compositions remain available when explicit team orchestration is warranted, for example feature development, bug investigation, code review, and UX audit.
</team_compositions>

---

<team_pipeline>
Team mode is the structured multi-agent surface.
Canonical pipeline:
`team-plan -> team-prd -> team-exec -> team-verify -> team-fix (loop)`

Use it when durable staged coordination is worth the overhead. Otherwise, stay direct.
Terminal states: `complete`, `failed`, `cancelled`.
</team_pipeline>

---

<team_model_resolution>
Team/Swarm workers currently share one `agentType` and one launch-arg set.
Model precedence:
1. Explicit model in `OMX_TEAM_WORKER_LAUNCH_ARGS`
2. Inherited leader `--model`
3. Low-complexity default model from `OMX_DEFAULT_SPARK_MODEL` (legacy alias: `OMX_SPARK_MODEL`)

Normalize model flags to one canonical `--model <value>` entry.
Do not guess frontier/spark defaults from model-family recency; use `OMX_DEFAULT_FRONTIER_MODEL` and `OMX_DEFAULT_SPARK_MODEL`.
</team_model_resolution>

<!-- OMX:MODELS:START -->
## Model Capability Table

Auto-generated by `omx setup` from the current `config.toml` plus OMX model overrides.

| Role | Model | Reasoning Effort | Use Case |
| --- | --- | --- | --- |
| Frontier (leader) | `gpt-5.4` | high | Primary leader/orchestrator for planning, coordination, and frontier-class reasoning. |
| Spark (explorer/fast) | `gpt-5.3-codex-spark` | low | Fast triage, explore, lightweight synthesis, and low-latency routing. |
| Standard (subagent default) | `gpt-5.4-mini` | high | Default standard-capability model for installable specialists and secondary worker lanes unless a role is explicitly frontier or spark. |
| `explore` | `gpt-5.3-codex-spark` | low | Fast codebase search and file/symbol mapping (fast-lane, fast) |
| `analyst` | `gpt-5.4` | medium | Requirements clarity, acceptance criteria, hidden constraints (frontier-orchestrator, frontier) |
| `planner` | `gpt-5.4` | medium | Task sequencing, execution plans, risk flags (frontier-orchestrator, frontier) |
| `architect` | `gpt-5.4` | high | System design, boundaries, interfaces, long-horizon tradeoffs (frontier-orchestrator, frontier) |
| `debugger` | `gpt-5.4-mini` | high | Root-cause analysis, regression isolation, failure diagnosis (deep-worker, standard) |
| `executor` | `gpt-5.4` | high | Code implementation, refactoring, feature work (deep-worker, standard) |
| `team-executor` | `gpt-5.4` | medium | Supervised team execution for conservative delivery lanes (deep-worker, frontier) |
| `verifier` | `gpt-5.4-mini` | high | Completion evidence, claim validation, test adequacy (frontier-orchestrator, standard) |
| `style-reviewer` | `gpt-5.3-codex-spark` | low | Formatting, naming, idioms, lint conventions (fast-lane, fast) |
| `quality-reviewer` | `gpt-5.4-mini` | medium | Logic defects, maintainability, anti-patterns (frontier-orchestrator, standard) |
| `api-reviewer` | `gpt-5.4-mini` | medium | API contracts, versioning, backward compatibility (frontier-orchestrator, standard) |
| `security-reviewer` | `gpt-5.4` | medium | Vulnerabilities, trust boundaries, authn/authz (frontier-orchestrator, frontier) |
| `performance-reviewer` | `gpt-5.4-mini` | medium | Hotspots, complexity, memory/latency optimization (frontier-orchestrator, standard) |
| `code-reviewer` | `gpt-5.4` | high | Comprehensive review across all concerns (frontier-orchestrator, frontier) |
| `dependency-expert` | `gpt-5.4-mini` | high | External SDK/API/package evaluation (frontier-orchestrator, standard) |
| `test-engineer` | `gpt-5.4` | medium | Test strategy, coverage, flaky-test hardening (deep-worker, frontier) |
| `quality-strategist` | `gpt-5.4-mini` | medium | Quality strategy, release readiness, risk assessment (frontier-orchestrator, standard) |
| `build-fixer` | `gpt-5.4-mini` | high | Build/toolchain/type failures resolution (deep-worker, standard) |
| `designer` | `gpt-5.4-mini` | high | UX/UI architecture, interaction design (deep-worker, standard) |
| `writer` | `gpt-5.4-mini` | high | Documentation, migration notes, user guidance (fast-lane, standard) |
| `qa-tester` | `gpt-5.4-mini` | low | Interactive CLI/service runtime validation (deep-worker, standard) |
| `git-master` | `gpt-5.4-mini` | high | Commit strategy, history hygiene, rebasing (deep-worker, standard) |
| `code-simplifier` | `gpt-5.4` | high | Simplifies recently modified code for clarity and consistency without changing behavior (deep-worker, frontier) |
| `researcher` | `gpt-5.4-mini` | high | External documentation and reference research (fast-lane, standard) |
| `product-manager` | `gpt-5.4-mini` | medium | Problem framing, personas/JTBD, PRDs (frontier-orchestrator, standard) |
| `ux-researcher` | `gpt-5.4-mini` | medium | Heuristic audits, usability, accessibility (frontier-orchestrator, standard) |
| `information-architect` | `gpt-5.4-mini` | low | Taxonomy, navigation, findability (frontier-orchestrator, standard) |
| `product-analyst` | `gpt-5.4-mini` | low | Product metrics, funnel analysis, experiments (frontier-orchestrator, standard) |
| `critic` | `gpt-5.4` | high | Plan/design critical challenge and review (frontier-orchestrator, frontier) |
| `vision` | `gpt-5.4` | low | Image/screenshot/diagram analysis (fast-lane, frontier) |
<!-- OMX:MODELS:END -->

---

<verification>
Verify before claiming completion.

Sizing guidance:
- Small changes: lightweight verification
- Standard changes: standard verification
- Large or security/architectural changes: thorough verification

<!-- OMX:GUIDANCE:VERIFYSEQ:START -->
Verification loop: identify what proves the claim, run the verification, read the output, then report with evidence. If verification fails, continue iterating rather than reporting incomplete work. Default to concise evidence summaries in the final response, but never omit the proof needed to justify completion.

- Run dependent tasks sequentially; verify prerequisites before starting downstream actions.
- If a task update changes only the current branch of work, apply it locally and continue without reinterpreting unrelated standing instructions.
- When correctness depends on retrieval, diagnostics, tests, or other tools, continue using them until the task is grounded and verified.
<!-- OMX:GUIDANCE:VERIFYSEQ:END -->
</verification>

<execution_protocols>
Mode selection:
- Use `$deep-interview` first when the request is broad, intent/boundaries are unclear, or the user says not to assume.
- Use `$ralplan` when the requirements are clear enough but architecture, tradeoffs, or test strategy still need consensus.
- Use `$team` when the approved plan has multiple independent lanes, shared blockers, or durable coordination needs.
- Use `$ralph` when the approved plan should stay in a persistent completion / verification loop with one owner.
- Otherwise execute directly in solo mode.
- Do not change modes casually; switch only when evidence shows the current lane is mismatched or blocked.

Command routing:
- When `USE_OMX_EXPLORE_CMD` enables advisory routing, strongly prefer `omx explore` as the default surface for simple read-only repository lookup tasks (files, symbols, patterns, relationships).
- For simple file/symbol lookups, use `omx explore` FIRST before attempting full code analysis.

When to use what:
- Use `omx explore --prompt ...` for simple read-only lookups.
- Use `omx sparkshell` for noisy read-only shell commands, bounded verification runs, repo-wide listing/search, or tmux-pane summaries; `omx sparkshell --tmux-pane ...` is explicit opt-in.
- Keep ambiguous, implementation-heavy, edit-heavy, or non-shell-only work on the richer normal path.
- `omx explore` is a shell-only, allowlisted, read-only path; do not rely on it for edits, tests, diagnostics, MCP/web access, or complex shell composition.
- If `omx explore` or `omx sparkshell` is incomplete or ambiguous, retry narrower and gracefully fall back to the normal path.

Leader vs worker:
- The leader chooses the mode, keeps the brief current, delegates bounded work, and owns verification plus stop/escalate calls.
- Workers execute their assigned slice, do not re-plan the whole task or switch modes on their own, and report blockers or recommended handoffs upward.
- Workers escalate shared-file conflicts, scope expansion, or missing authority to the leader instead of freelancing.

Stop / escalate:
- Stop when the task is verified complete, the user says stop/cancel, or no meaningful recovery path remains.
- Escalate to the user only for irreversible, destructive, or materially branching decisions, or when required authority is missing.
- Escalate from worker to leader for blockers, scope expansion, shared ownership conflicts, or mode mismatch.
- `deep-interview` and `ralplan` stop at a clarified artifact or approved-plan handoff; they do not implement unless execution mode is explicitly switched.

Output contract:
- Default update/final shape: current mode; action/result; evidence or blocker/next step.
- Keep rationale once; do not restate the full plan every turn.
- Expand only for risk, handoff, or explicit user request.

Parallelization:
- Run independent tasks in parallel.
- Run dependent tasks sequentially.
- Use background execution for builds and tests when helpful.
- Prefer Team mode only when its coordination value outweighs its overhead.
- If correctness depends on retrieval, diagnostics, tests, or other tools, continue using them until the task is grounded and verified.

Anti-slop workflow:
- Cleanup/refactor/deslop work still follows the same `$deep-interview` -> `$ralplan` -> `$team`/`$ralph` path; use `$ai-slop-cleaner` as a bounded helper inside the chosen execution lane, not as a competing top-level workflow.
- Lock behavior with tests first, then make one smell-focused pass at a time.
- Prefer deletion, reuse, and boundary repair over new layers.
- Keep writer/reviewer pass separation for cleanup plans and approvals.

Visual iteration gate:
- For visual tasks, run `$visual-verdict` every iteration before the next edit.
- Persist verdict JSON in `.omx/state/{scope}/ralph-progress.json`.

Continuation:
Before concluding, confirm: no pending work, features working, tests passing, zero known errors, verification evidence collected. If not, continue.

Ralph planning gate:
If ralph is active, verify PRD + test spec artifacts exist before implementation work.
</execution_protocols>

<cancellation>
Use the `cancel` skill to end execution modes.
Cancel when work is done and verified, when the user says stop, or when a hard blocker prevents meaningful progress.
Do not cancel while recoverable work remains.
</cancellation>

---

<state_management>
OMX persists runtime state under `.omx/`:
- `.omx/state/` — mode state
- `.omx/notepad.md` — session notes
- `.omx/project-memory.json` — cross-session memory
- `.omx/plans/` — plans
- `.omx/logs/` — logs

Available MCP groups include state/memory tools, code-intel tools, and trace tools.

Mode lifecycle requirements:
- Write state on start.
- Update state on phase or iteration change.
- Mark inactive with `completed_at` on completion.
- Clear state on cancel/abort cleanup.
</state_management>

---

## Setup

Run `omx setup` to install all components. Run `omx doctor` to verify installation.

# CNC Project Documentation for Agents

This repository contains code to control a CNC router (mill) using a Python-based driver that communicates over serial (GRBL).

## Key Components

### Source Code (`src/instrument_drivers/cnc_driver`)
- **`driver.py`**: Contains the `Mill` class, which is the main interface for controlling the CNC gantry.
    - **Usage**: Use `with Mill() as mill:` to connect.
    - **Methods**: `mill.move_to_position(x, y, z)`, `mill.home()`, `mill.current_coordinates()`.
- **`instruments.py`**: Defines `Coordinates`, `InstrumentManager`, and `Instruments`. Handles instrument offsets.
- **`mock.py`**: Contains `MockMill` for offline testing.

### Testing
- **`test_cnc_move.py`**: A sample script to move the CNC mill 1mm in the X direction.
    - **Run with**: `python3 test_cnc_move.py` (requires CNC connection)
- **`tests/verify_cnc_move.py`**: Verifies logic of the move script using mocks.

## Usage Guide for Agents

1.  **Connecting**: Always use the context manager `with Mill() as mill:` to ensure proper connection and cleanup.
2.  **Moving**: Use `mill.move_to_position(x, y, z)` for safe moves. The driver handles validation against the working volume (negative coordinates mostly).
    - **Coordinates**: The gantry typically operates in negative space relative to Home (0,0,0). e.g., X goes from 0 to -415.
3.  **Offsets**: Instruments have offsets managed by `InstrumentManager`.

### Instruments (`src/instruments`)
Base classes and instrument drivers for lab equipment.

- **`base_instrument.py`**: `BaseInstrument` abstract class and `InstrumentError`. All instrument drivers inherit from this.
- **`__init__.py`**: Exports `BaseInstrument`, `InstrumentError`.

#### Filmetrics (`src/instruments/filmetrics`)
Driver for the Filmetrics film thickness measurement system. Communicates with a C# console app (`FilmetricsTool.exe`) via stdin/stdout text commands.

- **`driver.py`**: `Filmetrics(BaseInstrument)` — the real driver.
    - **Constructor**: `Filmetrics(exe_path, recipe_name, command_timeout=30.0, name=None)`
    - **Lifecycle**: `connect()`, `disconnect()`, `health_check()`
    - **Commands**: `acquire_sample()`, `acquire_reference(ref)`, `acquire_background()`, `commit_baseline()`, `measure() -> MeasurementResult`, `save_spectrum(id)`
- **`mock.py`**: `MockFilmetrics` — in-memory mock for testing. Tracks `command_history: list[str]`.
- **`models.py`**: `MeasurementResult` frozen dataclass (`thickness_nm`, `goodness_of_fit`, `is_valid`).
- **`exceptions.py`**: `FilmetricsError` hierarchy (`FilmetricsConnectionError`, `FilmetricsCommandError`, `FilmetricsParseError`).
- **`reference/`**: Copy of the C# source (`FilmetricsTool_program.cs`) for protocol reference.

#### UV-Vis CCS Spectrometer (`src/instruments/uvvis_ccs`)
Driver for the Thorlabs CCS-series compact spectrometers (CCS100/CCS175/CCS200). Communicates with the instrument via the Thorlabs TLCCS DLL through ctypes. 3648-pixel linear CCD.

- **`driver.py`**: `UVVisCCS(BaseInstrument)` — the real DLL-based driver.
    - **Constructor**: `UVVisCCS(serial_number, dll_path="TLCCS_64.dll", default_integration_time_s=0.24, name=None)`
    - **Lifecycle**: `connect()`, `disconnect()`, `health_check()`
    - **Commands**: `set_integration_time(seconds)`, `get_integration_time()`, `measure() -> UVVisSpectrum`, `get_device_info()`
- **`mock.py`**: `MockUVVisCCS` — in-memory mock for testing. Tracks `command_history: list[str]`.
- **`models.py`**: `UVVisSpectrum` frozen dataclass (`wavelengths`, `intensities`, `integration_time_s`, `is_valid`, `num_pixels`). `NUM_PIXELS = 3648`.
- **`exceptions.py`**: `UVVisCCSError` hierarchy (`UVVisCCSConnectionError`, `UVVisCCSMeasurementError`, `UVVisCCSTimeoutError`).

#### Pipette (`src/instruments/pipette`)
Driver for Opentrons OT-2 and Flex pipettes. Communicates with the pipette motor via Arduino serial (Pawduino firmware). Supports 10 pipette models; the P300 single-channel has real calibrated values from PANDA-BEAR.

- **`driver.py`**: `Pipette(BaseInstrument)` — the real serial driver.
    - **Constructor**: `Pipette(pipette_model, port, baud_rate=115200, command_timeout=30.0, name=None)`
    - **Lifecycle**: `connect()`, `disconnect()`, `health_check()`, `warm_up()` (homes + primes)
    - **Commands**: `home()`, `prime(speed)`, `aspirate(volume_ul, speed)`, `dispense(volume_ul, speed)`, `blowout(speed)`, `mix(volume_ul, reps, speed)`, `pick_up_tip(speed)`, `drop_tip(speed)`, `get_status() -> PipetteStatus`, `drip_stop(volume_ul, speed)`
- **`mock.py`**: `MockPipette` — in-memory mock for testing. Tracks `command_history: list[str]`.
- **`models.py`**: `PipetteConfig` (frozen, per-model hardware description), `PipetteStatus`, `AspirateResult`, `MixResult` (all frozen dataclasses). `PIPETTE_MODELS` registry dict. `PipetteFamily` enum (OT2/FLEX).
- **`exceptions.py`**: `PipetteError` hierarchy (`PipetteConnectionError`, `PipetteCommandError`, `PipetteTimeoutError`, `PipetteConfigError`).

### Protocol Engine (`src/protocol_engine`)
A modular system for executing experiment sequences defined in code or YAML.

- **`protocol.py`**: `Protocol`, `ProtocolStep`, and `ProtocolContext` classes. `ProtocolContext` provides `board`, `deck`, and optionally `gantry` config to command handlers.
- **`yaml_schema.py`**: Pydantic schemas for protocol YAML (step validation against registered commands).
- **`loader.py`**: `load_protocol_from_yaml(path)` and `_safe` variant.
- **`registry.py`**: `CommandRegistry` singleton and `@protocol_command()` decorator for registering commands.
- **`setup.py`**: `setup_protocol(gantry_path, deck_path, board_path, protocol_path)` — loads all configs, validates bounds, and returns `(Protocol, ProtocolContext)` ready to run. Uses `OfflineGantry` by default for offline validation.
- **`commands/`**: Protocol command implementations (`move.py`, `pipette.py`, `scan.py`).

### Gantry Config (`src/gantry`)
Gantry YAML loader and domain model for CNC gantry working volume and homing strategy.

- **`yaml_schema.py`**: `GantryYamlSchema` with strict Pydantic validation (working volume bounds, homing strategy, serial port).
- **`gantry_config.py`**: `GantryConfig` and `WorkingVolume` frozen dataclasses. `WorkingVolume.contains(x, y, z)` checks if a point is within bounds (inclusive).
- **`loader.py`**: `load_gantry_from_yaml(path)` and `load_gantry_from_yaml_safe(path)`.
- **Config files**: `configs/gantries/` (e.g., `genmitsu_3018_PROver_v2.yaml`).

### Validation (`src/validation`)
Bounds validation for protocol setup — ensures all deck positions and gantry-computed positions are within the gantry's working volume before the protocol runs.

- **`bounds.py`**: `validate_deck_positions(gantry, deck)` and `validate_gantry_positions(gantry, deck, board)`. Returns lists of `BoundsViolation` objects. Gantry formula: `gantry_pos = deck_pos - instrument_offset`.
- **`errors.py`**: `BoundsViolation` dataclass and `SetupValidationError` exception with all violations listed.

### Deck and Labware (`src/deck`)
Deck configuration loading, runtime deck container, and labware geometry/positioning models.

- **`src/deck/deck.py`**: `Deck` class — runtime container holding labware loaded from deck YAML. Provides dict-like access (`deck["plate_1"]`, `len(deck)`, `"plate_1" in deck`) and `deck.resolve("plate_1.A1")` for target-to-coordinate resolution. The raw labware dict is accessible via `deck.labware`.
- **Labware models** (`src/deck/labware/`):
  - **`labware.py`**: `Coordinate3D` and `Labware` base model. `Labware` provides high-level shared behavior (e.g., `get_location`, `get_initial_position`) and common validation helpers; concrete required fields live in subclasses. All models use strict schema (`extra='forbid'`).
  - **`well_plate.py`**: `WellPlate(Labware)` for multi-well plates (e.g., SBS 96-well). Required fields include `name`, `model_name`, dimensions, layout (`rows`, `columns`), `wells`, and volume fields (`capacity_ul`, `working_volume_ul`). Also provides `get_well_center(well_id)`.
  - **`vial.py`**: `Vial(Labware)` for a single vial. Required fields include `name`, `model_name`, geometry (`height_mm`, `diameter_mm`), single `location`, and volume fields (`capacity_ul`, `working_volume_ul`), plus `get_vial_center()`.
- **Deck configuration (YAML)**: Deck layout is defined in a **deck YAML** file (labware only; no gantry settings). Strict schema: only allowed fields; missing, extra, or wrong-type fields raise `ValidationError`.
  - **`src/deck/yaml_schema.py`**: Pydantic models for deck YAML: `DeckYamlSchema` (root, single key `labware`), `WellPlateYamlEntry` (two-point calibration points under `calibration.a1` and `calibration.a2`, axis-aligned only), `VialYamlEntry` (single vial location). Both require `model_name`. All use `extra='forbid'`.
  - **`src/deck/loader.py`**: `load_deck_from_yaml(path)` loads a deck YAML file and returns a `Deck` containing all labware. Well plates are built from calibration A1/A2 and x/y offsets (derived well positions); vials from a single explicit `location`.
  - **`src/deck/errors.py`**: `DeckLoaderError` for user-facing loader failures.
- **Sample config**: `configs/decks/deck.sample.yaml` — one well plate and one vial; use as reference for required fields and two-point calibration format.
- **Usage**: Load a deck with `load_deck_from_yaml("configs/decks/deck.sample.yaml")` to get a `Deck` object. Access labware: `deck["plate_1"]`. Resolve targets: `deck.resolve("plate_1.A1")` for absolute XYZ.

### Config Directory Structure
Config files are organized by type:
```
configs/
  gantries/     # Gantry configs (serial port, homing, working volume)
  decks/        # Deck configs (labware positions)
  boards/       # Board configs (instrument offsets)
  protocols/    # Protocol configs (command sequences)
```

### Data Persistence (`data/`)
SQLite-backed persistence layer for self-driving lab campaigns. All state lives in the database — Python objects are stateless to survive interrupts/crashes.

- **`data/data_store.py`**: `DataStore` class — owns a SQLite connection and provides the full persistence API.
    - **Constructor**: `DataStore(db_path="data/databases/panda_data.db")` — opens/creates DB and initialises schema. Use `":memory:"` for testing.
    - **Empty template**: `data/databases/panda_data.db` — pre-initialized empty database committed to the repo for schema inspection (`sqlite3 data/databases/panda_data.db ".schema"`).
    - **Context manager**: `with DataStore(...) as store:` for automatic cleanup.
    - **Campaign API**: `create_campaign(description, deck_config=None, board_config=None, gantry_config=None, protocol_config=None) -> int`
    - **Experiment API**: `create_experiment(campaign_id, labware_name, well_id, contents_json=None) -> int`
    - **Measurement API**: `log_measurement(experiment_id, result) -> int` — dispatches by type:
        - `UVVisSpectrum` → `uvvis_measurements` (wavelengths/intensities stored as little-endian BLOB via `struct.pack`)
        - `MeasurementResult` → `filmetrics_measurements` (thickness_nm, goodness_of_fit)
        - `str` (image path) → `camera_measurements`
    - **Labware API** (volume and content tracking, persisted to `labware` table):
        - `register_labware(campaign_id, labware_key, labware)` — registers a Vial (1 row) or WellPlate (1 row per well) with total/working volume from the model.
        - `record_dispense(campaign_id, labware_key, well_id, source_name, volume_ul)` — increments `current_volume_ul` and appends to `contents` JSON.
        - `get_contents(campaign_id, labware_key, well_id) -> list | None` — returns parsed contents list.
    - **Schema tables**: `campaigns`, `experiments`, `uvvis_measurements`, `filmetrics_measurements`, `camera_measurements`, `labware`

#### Protocol Integration
- **`ProtocolContext.data_store`**: Optional `DataStore` instance. When set (along with `campaign_id`), `scan` and `transfer` commands automatically persist measurements and labware state.
- **`ProtocolContext.campaign_id`**: Optional `int`. FK to the `campaigns` table.
- Commands work identically when `data_store` is `None` — no code changes needed for existing protocols.

### Experiments
- **`experiments/`**: Directory for storing YAML experiment definitions.
- **`verify_experiment.py`**: Main runner script. Loads an experiment (YAML), compiles it, and executes it on the hardware.
    - **Usage**: `python verify_experiment.py [experiment_file.yaml]`

## Usage Guide for Agents

1.  **Defining Experiments**: Create a YAML file in `experiments/` defining the sequence of moves and images.
2.  **Running**: Execute `python verify_experiment.py experiments/your_experiment.yaml`.
3.  **Connecting**: The system handles connection details (port, serial) via config files in `configs/gantries/`, `configs/decks/`, `configs/boards/`, and `configs/protocols/`.

### Setup (`setup/`)
First-run scripts for verifying hardware after unboxing.

- **`hello_world.py`**: Interactive jog test. Connects to the gantry (auto-scan, no config), homes the gantry, then lets you move the router with arrow keys and see live position updates.
    - **Usage**: `python3 setup/hello_world.py`
    - **Controls**: Arrow keys (X/Y ±1mm), Z key (Z down 1mm), X key (Z up 1mm), Q (quit)
    - **Dependencies**: `src/hardware/gantry.py` (Gantry class)
- **`validate_setup.py`**: Validate a protocol setup by loading all 4 configs (gantry, deck, board, protocol) and checking that all deck and gantry positions are within the gantry's working volume.
    - **Usage**: `python setup/validate_setup.py <gantry.yaml> <deck.yaml> <board.yaml> <protocol.yaml>`
    - **Output**: Step-by-step loading status, labware/instrument summaries, bounds validation results, and a final PASS/FAIL verdict.
    - **Dependencies**: `src/gantry`, `src/deck`, `src/board`, `src/protocol_engine`, `src/validation`
- **`run_protocol.py`**: Load, validate, connect to hardware, and run a protocol end-to-end. Runs offline validation first, then connects to the gantry and executes the protocol.
    - **Usage**: `python setup/run_protocol.py <gantry.yaml> <deck.yaml> <board.yaml> <protocol.yaml>`
    - **Dependencies**: `src/gantry`, `src/deck`, `src/board`, `src/protocol_engine`, `src/validation`
- **`keyboard_input.py`**: Helper module that reads single keypresses (including arrow keys) without requiring Enter. Uses `tty`/`termios` (Unix only).

## Environment
- **Python**: 3.x
- **Dependencies**: `pyserial`, `opencv-python`, `pydantic`, `pyyaml`.

<!-- OMX:RUNTIME:START -->
<session_context>
**Session:** omx-1775483614732-58mbtt | 2026-04-06T13:53:34.781Z

**Explore Command Preference:** enabled via `USE_OMX_EXPLORE_CMD` (default-on; opt out with `0`, `false`, `no`, or `off`)
- Advisory steering only: agents SHOULD treat `omx explore` as the default first stop for direct inspection and SHOULD reserve `omx sparkshell` for qualifying read-only shell-native tasks.
- For simple file/symbol lookups, use `omx explore` FIRST before attempting full code analysis.
- When the user asks for a simple read-only exploration task (file/symbol/pattern/relationship lookup), strongly prefer `omx explore` as the default surface.
- Explore examples: `omx explore...

**Compaction Protocol:**
Before context compaction, preserve critical state:
1. Write progress checkpoint via state_write MCP tool
2. Save key decisions to notepad via notepad_write_working
3. If context is >80% full, proactively checkpoint state
</session_context>
<!-- OMX:RUNTIME:END -->
