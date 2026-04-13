# PR #11 Real Evolve And Docs Design

## Goal

在独立 Git worktree 中真实跑通 PR #11 引入的 tuned-agent evolution 流程，并把这套能力补充到 AgentFlow skill 和公开文档中。

## Scope

本次工作只覆盖 PR #11 相关能力：

- 真实执行一次 `agentflow evolve`，目标为 `codex` profile
- 验证生成出的 tuned agent 已注册到 `.agentflow/tuned_agents`
- 尽量用生成出的 tuned agent 再跑一个最小节点，证明运行时可解析并调用它
- 更新 `skills/agentflow/SKILL.md`
- 更新公开文档，至少包括根 `README.md`、`docs/cli.md`，必要时同步 `docs/README.md`

不在本次范围内：

- 新增新的 CLI 子命令
- 新增独立的 demo app 或复杂 example
- 引入新的持续集成慢测试框架，除非真实跑通过程暴露出必须修复的问题

## Current State

当前 `master` 已包含 commit `eca49a6`，标题为 `Add tuned agent evolution and Codex tuner profile (#11)`。代码已经具备这些能力：

- `agentflow.evolve(...)` DSL helper 可以把 trace 路径封装为 evolution payload
- `python -m agentflow evolve` / `tuned-agents` / `tuned-agent` CLI 已存在
- `agentflow/tuned_agents.py` 已实现 profile 读取、repo clone、optimizer 调用、build/test/smoke、registry/version 注册
- `agent_tuner/codex.yaml` 已定义 Codex tuned-agent profile
- `tests/test_tuned_agents.py` 已覆盖主要单元和集成路径

当前缺口不在“功能是否合并”，而在“是否已经被真实完整验证”和“外部用户是否知道怎么使用”。

## User-Visible Outcome

交付完成后，项目应具备以下可验证结果：

1. 开发者可以在本地先跑出一个含 `codex` trace 的 AgentFlow run，再执行 `python -m agentflow evolve <run_id> -n <node_id> --target codex --profile codex --optimizer codex`。
2. evolve 成功后，`.agentflow/tuned_agents` 下出现新版本目录和 registry 记录。
3. `python -m agentflow tuned-agents` 能列出该 tuned agent，`python -m agentflow tuned-agent <name>` 能返回详情。
4. 文档能明确告诉用户：
   - 先决条件是什么
   - 真实执行顺序是什么
   - 产物会落在哪里
   - 当前限制是什么，例如 tuned agent 目前要求 local target

## Implementation Approach

### 1. Isolated execution first

所有开发和验证都只在 `.worktrees/<branch>` 中进行，避免污染主工作区。

### 2. Baseline before fixes

先确认现有测试基线，再开始真实 evolve。如果真实流程失败，优先判断是环境问题、文档缺失，还是代码 bug；只有代码 bug 才进入修复。

### 3. Real trace -> evolve -> registry -> reuse

真实运行应遵守这条链路：

1. 运行一个最小 pipeline，产出 `codex` 节点 trace
2. 从 `.agentflow/runs/<run_id>` 或 `agentflow runs/show` 中拿到 `run_id` / `node_id`
3. 执行 `agentflow evolve`
4. 检查 `.agentflow/tuned_agents`
5. 查询 tuned-agent CLI
6. 用生成出的 tuned agent 再跑一个最小节点

### 4. Docs follow verified behavior

文档只写已被实际验证过的命令、输出路径、限制和前置条件，不写推测性说明。

## Files Likely To Change

- `README.md`
- `docs/README.md`
- `docs/cli.md`
- `skills/agentflow/SKILL.md`

如果真实执行暴露代码问题，可能还会改：

- `agentflow/tuned_agents.py`
- `agentflow/cli.py`
- `agentflow/orchestrator.py`
- `tests/test_tuned_agents.py`

## Validation Plan

最低验收要求：

- `python -m pytest tests/test_tuned_agents.py -q`
- 成功执行一次真实 `python -m agentflow evolve ...`
- 成功查询 `python -m agentflow tuned-agents`
- 成功查询 `python -m agentflow tuned-agent <generated-name>`
- 若环境允许，成功运行一个 `agent="codex_tuned"` 的最小 pipeline
- Skill 和公开文档都更新，并与真实行为一致

## Risks

- `agent_tuner/codex.yaml` 指向 `https://github.com/openai/codex.git`，因此真实 evolve 依赖外网和 GitHub 可访问性
- 该 profile 会运行 `cargo build` / `cargo test`，因此依赖 Rust toolchain 和相应系统环境
- optimizer 使用本机 `codex`，如果鉴权或 CLI 行为不稳定，真实 evolve 可能失败
- tuned agent 当前只支持 local target；文档必须明确这个限制
