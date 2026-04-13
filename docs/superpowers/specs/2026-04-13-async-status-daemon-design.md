# Async Status Daemon Design

**Problem**

`agentflow run` currently submits a run and then blocks until completion in the foreground CLI process. `Orchestrator.submit()` already schedules background work, but the worker thread is a daemon thread owned by the current process, so `agentflow run -d` cannot work by simply skipping `wait()`. The process would exit and the run would die.

**User-facing goal**

- `agentflow run pipeline.py -d` submits a run, returns a stable `run_id`, and exits immediately.
- `agentflow status <run_id>` shows in-flight progress, not only the final result.
- The status view must be able to show PR11 evolution process details and PR12 graph-optimization process details.

**Design**

1. Detached execution uses a long-lived local daemon based on the existing FastAPI app and `Orchestrator`, rather than a per-run child process. The CLI becomes a thin client for detached submission.
2. The daemon lifecycle is managed in-process by new CLI helpers that persist a small daemon metadata file next to the run store and auto-start `agentflow serve` in the background when needed.
3. `status` is a new CLI command. It reads the persistent run store directly for run data and events, so historical runs remain inspectable even if the daemon is offline.
4. PR12 support is brought into this branch by porting the graph optimization runtime model: `optimization_session`, parent/child run relationships, round events, and child-run bookkeeping.
5. PR11 process visibility is added by instrumenting `run_evolution_from_payload()` with progress callbacks and making the generated `dsl.evolve()` Python node emit structured progress lines to stderr. `status` interprets those lines into an evolution timeline.

**Scope**

- Implement detached run submission.
- Implement daemon auto-start helpers and metadata.
- Implement `status`.
- Port PR12 graph optimization support.
- Add PR11 evolution progress reporting for pipeline-driven evolution nodes.

**Out of scope**

- Reworking `agentflow evolve` into a fully orchestrated standalone run type with its own detached lifecycle.
- Merging the worktree branch back to `master`.

**Architecture**

- CLI detached submission:
  - Ensure daemon running for a given `runs_dir`.
  - Submit pipeline via existing HTTP `POST /api/runs`.
  - Print queued/running run summary with `run_id`.
- CLI status:
  - Build `RunStore(runs_dir)`.
  - Load `RunRecord` + `events.jsonl`.
  - Render a richer process summary and JSON payload.
- Graph optimization:
  - Port the PR12 `optimization_session` fields, round directories, and optimization events so status has first-class data to render.
- Evolution process:
  - Add a callback-based progress API in `agentflow.tuned_agents`.
  - Emit structured phase lines from generated evolve-node Python code.
  - Parse and surface them in status output.

**Testing**

- Add targeted CLI tests for `run -d`, daemon reuse, and `status`.
- Add targeted API/daemon helper tests where useful.
- Port/enable graph optimization tests from PR12.
- Add evolution progress/status tests for PR11-related process display.

