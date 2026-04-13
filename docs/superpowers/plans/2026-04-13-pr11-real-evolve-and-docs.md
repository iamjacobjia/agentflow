# PR #11 Real Evolve And Docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在独立 worktree 中真实跑通一次 PR #11 的 Codex tuned-agent evolve 流程，并把这套能力补充到 skill 和公开文档。

**Architecture:** 先建立测试与运行基线，再用最小真实 pipeline 产出 codex trace，接着执行真实 `agentflow evolve` 并验证 registry 与 tuned-agent 查询。最后把经过验证的命令、前置条件、限制和产物路径同步到 skill 与公开文档；如真实流程暴露 bug，则用最小修复补齐并回归验证。

**Tech Stack:** Python, pytest, Typer CLI, AgentFlow DSL, local Codex CLI, Git worktrees, Rust/cargo

---

### Task 1: Baseline And Real Evolve Reproduction

**Files:**
- Create: `tmp/pr11-real-evolve/pipeline.py`
- Create: `tmp/pr11-real-evolve/tuned-pipeline.py`
- Modify: `docs/superpowers/specs/2026-04-13-pr11-real-evolve-and-docs-design.md`
- Modify: `docs/superpowers/plans/2026-04-13-pr11-real-evolve-and-docs.md`

- [ ] **Step 1: Verify the current tuned-agent test baseline**

Run:

```bash
python -m pytest tests/test_tuned_agents.py -q
```

Expected: all tests pass on the new worktree before any code changes.

- [ ] **Step 2: Write a minimal real pipeline that produces a Codex trace**

```python
from agentflow import Graph, codex

with Graph("pr11-real-evolve-source") as g:
    codex(
        task_id="plan",
        prompt="Reply with exactly one short sentence describing this repository.",
        tools="read_only",
    )

print(g.to_json())
```

Save as `tmp/pr11-real-evolve/pipeline.py`.

- [ ] **Step 3: Run the source pipeline and capture the run id**

Run:

```bash
python -m agentflow run tmp/pr11-real-evolve/pipeline.py --output summary
python -m agentflow runs
```

Expected: one completed run exists and `.agentflow/runs/<run_id>/nodes/plan/artifacts/trace.jsonl` is present.

- [ ] **Step 4: Execute real evolve against the captured Codex trace**

Run:

```bash
python -m agentflow evolve <run_id> -n plan --target codex --profile codex --optimizer codex --output summary
```

Expected: clone/build/test/smoke complete successfully and output includes a tuned agent name, version, executable, and repo path.

- [ ] **Step 5: Verify registry and tuned-agent lookup**

Run:

```bash
python -m agentflow tuned-agents
python -m agentflow tuned-agent codex_tuned --output json
```

Expected: `tuned-agents` lists `codex_tuned`, and `tuned-agent` returns JSON containing the latest version metadata.

- [ ] **Step 6: Write a minimal pipeline that uses the generated tuned agent**

```python
from agentflow import Graph, agent

with Graph("pr11-real-evolve-verify") as g:
    agent(
        "codex_tuned",
        task_id="verify",
        prompt="Reply with exactly the word READY.",
    )

print(g.to_json())
```

Save as `tmp/pr11-real-evolve/tuned-pipeline.py`.

- [ ] **Step 7: Run the tuned-agent pipeline**

Run:

```bash
python -m agentflow run tmp/pr11-real-evolve/tuned-pipeline.py --output summary
```

Expected: the run completes and proves AgentFlow can resolve and execute the tuned agent.

- [ ] **Step 8: If any real-evolve step fails because of product code, capture the exact failure and stop treating this as docs-only**

Run:

```bash
python -m agentflow inspect tmp/pr11-real-evolve/tuned-pipeline.py --output summary
```

Expected: enough evidence to identify whether the failure is environment, documentation, or product code.

### Task 2: Fix Any Product Gaps Revealed By Real Execution

**Files:**
- Modify: `agentflow/tuned_agents.py`
- Modify: `agentflow/cli.py`
- Modify: `agentflow/orchestrator.py`
- Modify: `agentflow/inspection.py`
- Test: `tests/test_tuned_agents.py`

- [ ] **Step 1: Add a failing regression test for the real failure before touching product code**

```python
def test_regression_for_real_pr11_failure():
    raise AssertionError("replace with the real failure once reproduced")
```

Save it in `tests/test_tuned_agents.py` near the closest existing scenario.

- [ ] **Step 2: Run only the new regression test and confirm it fails for the intended reason**

Run:

```bash
python -m pytest tests/test_tuned_agents.py -q -k real_pr11_failure
```

Expected: FAIL due to the reproduced issue, not due to syntax or import mistakes.

- [ ] **Step 3: Implement the smallest product fix that makes the regression pass**

```python
# Use the smallest code change that directly addresses the reproduced failure.
# Do not broaden scope beyond the failing real-evolve path.
```

- [ ] **Step 4: Re-run the focused regression and then the tuned-agent suite**

Run:

```bash
python -m pytest tests/test_tuned_agents.py -q -k real_pr11_failure
python -m pytest tests/test_tuned_agents.py -q
```

Expected: both commands pass.

- [ ] **Step 5: Re-run the real evolve flow end-to-end**

Run:

```bash
python -m agentflow evolve <run_id> -n plan --target codex --profile codex --optimizer codex --output summary
python -m agentflow tuned-agents
python -m agentflow tuned-agent codex_tuned --output json
```

Expected: the original real-world failure no longer occurs.

### Task 3: Update Skill And Public Documentation

**Files:**
- Modify: `skills/agentflow/SKILL.md`
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/cli.md`

- [ ] **Step 1: Update the skill with tuned-agent concepts and usage order**

Add guidance covering:

```text
1. Run a pipeline that produces a codex trace.
2. Call agentflow.evolve(...) in DSL or python -m agentflow evolve ... in CLI.
3. Inspect .agentflow/tuned_agents plus tuned-agents/tuned-agent commands.
4. Reuse the generated tuned agent via agent("codex_tuned", ...).
5. Mention the current limitation: tuned agents require local target.
```

- [ ] **Step 2: Update the root README with a concise public overview**

Add a short section showing:

```bash
python -m agentflow evolve <run_id> -n <node_id> --target codex --profile codex --optimizer codex
python -m agentflow tuned-agents
python -m agentflow tuned-agent codex_tuned
```

and explain what `.agentflow/tuned_agents` contains.

- [ ] **Step 3: Update docs/cli.md with the actual command flow**

Document:

```text
- evolve arguments and when run_id/node_id come from prior runs
- tuned-agents and tuned-agent behavior
- expected prerequisites: local codex auth, network access, Rust/cargo for codex profile
```

- [ ] **Step 4: Update docs/README.md so the tuned-agent docs are discoverable**

Add a navigation bullet pointing readers to the CLI/tuned-agent guidance.

- [ ] **Step 5: Verify docs match the implemented behavior**

Run:

```bash
python -m agentflow --help
python -m agentflow evolve --help
python -m agentflow tuned-agents --help
python -m agentflow tuned-agent --help
```

Expected: command names and options in docs match actual CLI output.

### Task 4: Final Verification And Handoff

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`
- Modify: `docs/cli.md`
- Modify: `skills/agentflow/SKILL.md`
- Test: `tests/test_tuned_agents.py`

- [ ] **Step 1: Run the full targeted verification set**

Run:

```bash
python -m pytest tests/test_tuned_agents.py -q
python -m agentflow tuned-agents
python -m agentflow tuned-agent codex_tuned --output json
python -m agentflow run tmp/pr11-real-evolve/tuned-pipeline.py --output summary
```

Expected: all commands succeed with the tuned agent already registered.

- [ ] **Step 2: Record the exact evidence to report back**

Collect:

```text
- worktree path and branch
- evolve command used
- generated tuned-agent name/version
- files changed
- verification commands and outcomes
```

- [ ] **Step 3: Leave the branch unmerged for human review**

Run:

```bash
git status --short
git log --oneline -n 5
```

Expected: all work remains on the worktree branch only, ready for human review and manual PR creation.
