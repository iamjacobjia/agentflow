# Async Status Daemon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add detached AgentFlow execution with `agentflow run ... -d`, a new `agentflow status <id>` process view, PR11 evolution progress visibility, and PR12 graph optimization runtime support in an isolated worktree branch.

**Architecture:** Detached runs will be submitted to a long-lived local daemon built on the existing FastAPI app and `Orchestrator`, while `status` will read the persistent run store directly. PR12 graph optimization support will be ported into this branch so optimization runs generate first-class round/session data, and PR11 evolution will emit structured progress lines for status rendering.

**Tech Stack:** Python, Typer, FastAPI, httpx, pytest, existing `RunStore`/`Orchestrator` runtime.

---

### Task 1: Port PR12 Graph Optimization Runtime

**Files:**
- Create: `agentflow/graph_optimizer.py`
- Modify: `agentflow/specs.py`
- Modify: `agentflow/orchestrator.py`
- Test: `tests/test_graph_optimizer.py`

- [ ] **Step 1: Add the failing graph optimization tests**

Port the PR12 graph-optimization tests into a new test file covering:
- successful multi-round optimization
- retry on invalid optimized pipeline
- failure after exhausting optimizer validation attempts

Run:

```bash
pytest tests/test_graph_optimizer.py -q
```

Expected: FAIL because the current branch does not define graph-optimization runtime support.

- [ ] **Step 2: Add graph optimization data model support**

Implement the `PipelineSpec` and `RunRecord` fields needed for graph optimization:
- `optimizer`
- `n_run`
- `uses_graph_optimizer`
- `optimization_parent_run_id`
- `optimization_round`
- `optimization_session`

Run:

```bash
pytest tests/test_graph_optimizer.py -q
```

Expected: FAIL later in orchestrator/runtime paths instead of schema/attribute errors.

- [ ] **Step 3: Add graph optimization runtime helpers and orchestrator flow**

Port the PR12 runtime pieces:
- editable pipeline artifact generation
- graph report generation
- optimization round directories
- child run creation
- round/session events
- optimizer retry/accept/failure flow

Run:

```bash
pytest tests/test_graph_optimizer.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit the graph optimization runtime**

```bash
git add agentflow/graph_optimizer.py agentflow/specs.py agentflow/orchestrator.py tests/test_graph_optimizer.py
git commit -m "feat: port graph optimization runtime support"
```

### Task 2: Add Detached Daemon Submission

**Files:**
- Modify: `agentflow/cli.py`
- Modify: `tests/test_cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Add failing CLI tests for detached run submission**

Add tests for:
- `agentflow run pipeline.py -d` returning a queued/running `run_id` without waiting
- auto-start or reuse of the local daemon client path
- output shape for summary/json/json-summary detached results

Run:

```bash
pytest tests/test_cli.py -q -k "detach or daemon"
```

Expected: FAIL because `run` has no detach mode and no daemon submission helpers.

- [ ] **Step 2: Implement daemon metadata and ensure-daemon helpers**

Add CLI-side helpers that:
- compute a daemon metadata file path per `runs_dir`
- probe health on the configured host/port
- start `agentflow serve` in the background when needed
- wait until the daemon is reachable

- [ ] **Step 3: Implement `run -d`**

Update CLI `run` so:
- default mode keeps existing synchronous behavior
- `-d/--detach` loads the pipeline, ensures the daemon, submits via HTTP, prints the returned run record summary, and exits without waiting

Run:

```bash
pytest tests/test_cli.py -q -k "detach or daemon"
```

Expected: PASS.

- [ ] **Step 4: Commit detached submission**

```bash
git add agentflow/cli.py tests/test_cli.py
git commit -m "feat: add detached daemon-backed run submission"
```

### Task 3: Add `agentflow status <id>`

**Files:**
- Modify: `agentflow/cli.py`
- Modify: `tests/test_cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Add failing tests for `status`**

Add tests covering:
- missing run handling
- summary rendering for in-flight runs
- JSON summary payload including events and active node progress
- PR12 optimization-session visibility

Run:

```bash
pytest tests/test_cli.py -q -k "status_command or run_status"
```

Expected: FAIL because there is no `status` command or status renderer.

- [ ] **Step 2: Implement status builders and renderers**

Add new helpers that:
- load run + events from `RunStore`
- render process-oriented summaries
- include event timeline slices
- surface optimization session and round info when present

- [ ] **Step 3: Add the `status` command**

Implement a new Typer command:
- `agentflow status <run_id>`
- uses direct store reads rather than daemon queries for persistent inspection
- supports existing output styles plus richer JSON summary

Run:

```bash
pytest tests/test_cli.py -q -k "status_command or run_status"
```

Expected: PASS.

- [ ] **Step 4: Commit status command**

```bash
git add agentflow/cli.py tests/test_cli.py
git commit -m "feat: add run status process view"
```

### Task 4: Add PR11 Evolution Progress Visibility

**Files:**
- Modify: `agentflow/tuned_agents.py`
- Modify: `agentflow/dsl.py`
- Modify: `agentflow/cli.py`
- Modify: `tests/test_tuned_agents.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Add failing tests for evolution progress reporting**

Add tests covering:
- `run_evolution_from_payload()` progress callback/stage notifications
- `dsl.evolve()` generated node code emitting structured progress lines
- `status` rendering evolution stage lines from run artifacts/events or trace-derived data

Run:

```bash
pytest tests/test_tuned_agents.py tests/test_cli.py -q -k "evolution_progress or evolve_status"
```

Expected: FAIL because no structured evolution progress reporting exists.

- [ ] **Step 2: Implement progress callback support in tuned agent evolution**

Update `run_evolution_from_payload()` to report:
- start
- attempt start
- optimizer/build/test/smoke start and completion/failure
- final success/failure

- [ ] **Step 3: Emit progress lines from pipeline-driven evolve nodes**

Update `dsl.evolve()` generated Python code so pipeline execution emits structured progress lines to stderr while preserving the final stdout JSON result.

- [ ] **Step 4: Surface evolution progress in status rendering**

Teach status rendering to recognize and show evolution phase lines from the run’s stored trace/stderr data.

Run:

```bash
pytest tests/test_tuned_agents.py tests/test_cli.py -q -k "evolution_progress or evolve_status"
```

Expected: PASS.

- [ ] **Step 5: Commit evolution progress support**

```bash
git add agentflow/tuned_agents.py agentflow/dsl.py agentflow/cli.py tests/test_tuned_agents.py tests/test_cli.py
git commit -m "feat: surface evolution progress in run status"
```

### Task 5: End-to-End Verification

**Files:**
- Modify: `tests/test_api.py`
- Test: `tests/test_api.py`
- Test: `tests/test_graph_optimizer.py`
- Test: `tests/test_tuned_agents.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Add or adjust integration tests if needed**

Add focused API/integration coverage only where the earlier tasks reveal missing protection, especially around detached run submission paths and optimization session payload shape.

- [ ] **Step 2: Run the focused verification suite**

Run:

```bash
pytest tests/test_api.py tests/test_graph_optimizer.py tests/test_tuned_agents.py tests/test_cli.py -q
```

Expected: PASS for all tests added or touched by this feature. Pre-existing unrelated failures elsewhere in the repo are explicitly out of scope.

- [ ] **Step 3: Commit verification-only follow-ups**

```bash
git add tests/test_api.py tests/test_graph_optimizer.py tests/test_tuned_agents.py tests/test_cli.py
git commit -m "test: cover async status daemon flows"
```
