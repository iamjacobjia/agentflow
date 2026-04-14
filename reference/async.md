# AgentFlow Async 主线需求分析与实现说明

本文档基于 **2026-04-14 当前 `master`** 的代码状态撰写。

和前一版不同的是：

- PR11 已经在主线上。
- PR12 也已经在主线上。
- 因此这里不再讨论“要不要先把 PR12 合并进来”，而是直接基于 **已包含 PR11 + PR12 的 master** 分析老板需求，并记录这条主线任务在 `feat/async-status-masterline` worktree 分支里的实现结果。

---

## 1. 老板需求的真实含义

老板原始要求可以拆成四个不可分割的子目标：

1. `agentflow run pipeline.py -d` 必须返回一个稳定的任务 id。
2. CLI 退出后，任务必须继续真实执行，不能是假 detach。
3. `agentflow status <id>` 必须能查看运行中的任务，而不是只看最终结果。
4. `status` 必须能显示 PR11 / PR12 对应的过程信息，而不是只有普通节点的 completed/failed。

这四个目标里，最容易被误判的是第 2 点。

如果只是把当前 `run` 命令里的 `wait()` 去掉，CLI 虽然会立刻退出，但 `Orchestrator.submit()` 当前起的是 **daemon thread**，线程生命周期依附提交它的 Python 进程；进程一退出，run 也会死掉。这种做法不满足老板要的 async，只能算假象。

所以这次任务不是“给 CLI 加一个 `-d` 参数”那么简单，而是要把 AgentFlow 从“前台同步命令”提升成“支持后台宿主、支持 detached 提交、支持按 run_id 查看过程”的系统。

---

## 2. 基于 master 的现状分析

### 2.1 已经存在的能力

当前 `master` 已经具备下面这些关键基础设施：

- `RunStore`
  - 目录：`.agentflow/runs/<run_id>/`
  - 产物：`run.json`、`events.jsonl`、artifacts
  - 支持进程重启后从磁盘重新加载已有 runs
- `Orchestrator`
  - `submit()` 创建 run
  - `run()` 异步调度节点
  - `cancel()` / `rerun()` 已存在
- Web/API 层
  - `POST /api/runs`
  - `GET /api/runs/{id}`
  - `GET /api/runs/{id}/events`
  - `GET /api/runs/{id}/stream`
  - `POST /api/runs/{id}/cancel`
  - `POST /api/runs/{id}/rerun`
- CLI 已有
  - `runs`
  - `show`
  - `cancel`
  - `rerun`
  - `serve`

这意味着本次任务不需要从零发明 run store、event model 或 status 数据结构。

### 2.2 当前真正缺的能力

即便上述能力都在，当前 `master` 在老板的需求上仍然有三个核心缺口：

#### 缺口 A：`run` 默认是同步阻塞

`agentflow/cli.py` 里的 `run()` 仍然会：

1. load pipeline
2. `orchestrator.submit(pipeline)`
3. `orchestrator.wait(run_id)`
4. 等完成后再输出结果

因此当前 `run` 不是“提交任务”，而是“提交并等待完成”。

#### 缺口 B：没有真正的 detached execution host

`Orchestrator.submit()` 虽然起后台线程，但线程跟着当前 CLI 进程走。

也就是说：

- 当前没有真正的本地 daemon / background host
- CLI 退出后，提交出去的 run 也会跟着退出

#### 缺口 C：没有真正的 `status`

`show` 只能看静态 run 摘要，不是过程视图。

它无法完整表达：

- 最近事件时间线
- 正在跑哪些节点
- 当前进度
- optimization session / round / child runs
- evolution 过程阶段

因此老板要的 `status` 必须是新增语义，而不是把 `show` 改个名字。

---

## 3. PR11 / PR12 在 master 中的地位

### 3.1 PR11：tuned-agent evolution 已在主线

PR11 给主线带来了：

- `agentflow/tuned_agents.py`
- `run_evolution_from_payload()`
- `agentflow.dl.evolve()` / `agentflow evolve`
- tuned agent registry / profile / evolution 流程

但是 master 在本次任务前的一个明显不足是：

- evolution 虽然能跑
- 但 pipeline 中 evolve 节点的内部阶段并不会被 `status` 友好展示

具体来说，原始 master 只能看到 evolve 节点“在跑”或“结束”，看不到：

- 第几次 attempt
- 现在在 optimizer / build / test / smoke 哪一步
- 某一步失败的原因

所以老板说“需要能显示 PR11 的过程”时，实际要求的是 **evolution 运行时需要有结构化进度信号**。

### 3.2 PR12：graph optimization 已在主线

PR12 现在已经在 master 中，主线已经具备：

- `agentflow/graph_optimizer.py`
- `PipelineSpec.optimizer`
- `PipelineSpec.n_run`
- `PipelineSpec.uses_graph_optimizer`
- `RunRecord.optimization_parent_run_id`
- `RunRecord.optimization_round`
- `RunRecord.optimization_session`
- orchestrator 中的 `optimization_*` 事件与 round/session 逻辑

这意味着：

- `status` 不需要“等待 PR12 数据模型以后再做”
- 它现在就应该直接消费这些字段和事件
- 老板说的“显示 PR12 过程”在当前 master 上是一个**可以直接落地的主线需求**

---

## 4. 推荐方案（现已全部采纳）

你已经明确要求：**所有我推荐的方案都采纳，不需要再选择。**

因此这里直接把最终方案写清楚：

### 4.1 方案总览

#### 方案 1：复用 `serve` / FastAPI 作为本地后台宿主

这是主线方案，已经采纳并实现。

原因：

- 与现有 `RunStore` / `Orchestrator` / API 完全兼容
- 不需要再造一套 IPC 协议
- 与 agent-browser 的 client-daemon 思路一致
- 比“每个 run 自己 fork 一个孤立子进程”更系统、更可维护

#### 方案 2：`status` 直接读 store，而不是强依赖 daemon API

这也是主线方案，已经采纳并实现。

原因：

- `RunStore` 本来就是持久化真相源
- 历史 run 不该依赖 daemon 在线
- 这样可以把“执行宿主”和“状态读取”解耦

最终职责划分是：

- **运行执行**：依赖 daemon
- **状态查看**：优先直接读 store

#### 方案 3：PR11 进度用结构化 evolution progress 事件表达

这也是主线方案，已经采纳并实现。

原因：

- 不改动 standalone `agentflow evolve` 的返回协议
- 不强迫 evolve 变成独立 orchestrated run
- 只为 pipeline 中的 evolve 节点补上结构化进度轨迹

#### 方案 4：PR12 直接基于主线现有 optimization session / round 模型来展示

这也是主线方案，已经采纳并实现。

原因：

- master 已经有这些数据
- 没必要搞第二套 ad hoc 的 round 状态拼装

---

## 5. 实际实现结果

下面是基于当前 `master` 的主线任务，在 `feat/async-status-masterline` worktree 分支里已经完成的内容。

### 5.1 Detached execution：`agentflow run -d`

已实现：

- `agentflow run pipeline.py -d`
- 走本地 daemon 路径提交 run
- 通过已有 `POST /api/runs` 提交
- 不再等待 `wait()`
- 立即返回 run record

实现方式：

- CLI 增加 daemon helper
  - daemon metadata path
  - host/port 解析
  - 健康探测
  - 自动启动 `agentflow serve`
- `run -d` 分支提交到 daemon，再直接输出返回的 `RunRecord`

这样做的意义是：

- detach 不再是假象
- run 生命周期不再绑定提交它的那个前台 CLI

### 5.2 新增 `agentflow status <id>`

已实现：

- 新增 `status` 命令
- 不依赖 daemon HTTP 读取状态
- 直接用 `RunStore` 从磁盘读取 `RunRecord` + `events.jsonl`

`status` 当前支持：

- summary 输出
- json-summary 输出
- 进度统计
- 最近事件时间线
- optimization session 可见性
- evolution progress 可见性

它和 `show` 的分工现在是：

- `show`：静态摘要，保持原语义
- `status`：过程视图，强调 in-flight 运行态与时间线

### 5.3 PR11：evolution progress 可见

已实现：

- `run_evolution_from_payload()` 增加了 **可选** progress callback
- `dsl.evolve()` 生成的 python node 会把 progress 结构化 JSON 写到 stderr
- `status` 会从 node 的 `stderr_lines` 里解析这些 JSON

使用的稳定字段是：

- `agentflow_event: "evolution_progress"`
- `stage`
- `attempt`
- 可选 `status`
- 可选 `command`
- 可选 `detail`

现在 `status` 已经能显示：

- evolution start
- attempt started
- optimizer started/completed/failed
- build started/completed/failed
- test started/completed/failed
- smoke started/completed/failed
- final success/failed

并且后续又补上了一个重要细节：

- evolution progress 在 `status` 中会带 `node_id`

这样如果一个 run 里有多个 evolve 节点，不会混淆。

### 5.4 PR12：optimization session / rounds 可见

已实现：

- `status` summary 会显示 optimization 概况
  - kind
  - optimizer
  - current round / total rounds
  - child run 数量
- `json-summary` 会把 optimization 相关字段完整带上

这意味着老板要的“PR12 过程展示”已经不是纸面支持，而是 CLI process view 的一部分。

### 5.5 补上的一个主线健壮性修复

基于 master 的 PR12 代码，我额外补了一处必须的健壮性修复：

- 优化器编辑产物在校验前会被归一化为 child-run 形态：
  - `optimizer=None`
  - `n_run=1`

原因是：

- optimization prompt 允许模型改“iteration controls”
- 但如果模型把 `n_run` 改大，又没带合法 `optimizer`
- 原始 master 会在 schema 校验阶段直接炸掉，导致 optimization session 出现非必要失败

这个修复不是“补丁式救火”，而是保证 PR12 主线模型在真实 LLM 编辑场景下能够稳定工作。

---

## 6. 涉及的核心代码点

本次主线任务实际涉及的重点文件如下：

### 6.1 CLI / daemon / status

- `agentflow/cli.py`
  - detached daemon helpers
  - `run -d`
  - `status`
  - status summary / json-summary 渲染
  - evolution progress 解析与展示

### 6.2 PR11 evolution 进度

- `agentflow/tuned_agents.py`
  - `run_evolution_from_payload(..., progress=...)`
- `agentflow/dsl.py`
  - `evolve()` 生成的 python node stderr progress emission

### 6.3 PR12 optimization 健壮性

- `agentflow/graph_optimizer.py`
  - child pipeline loading / normalization
- `agentflow/orchestrator.py`
  - optimization round 中改为使用归一化后的 child pipeline loader
- `tests/test_graph_optimizer.py`
  - 覆盖 `n_run` 被模型改动时仍能继续 optimization session

### 6.4 测试

- `tests/test_cli.py`
  - detach 提交
  - status summary/json
  - optimization visibility
  - evolution progress visibility
- `tests/test_tuned_agents.py`
  - progress callback
- `tests/test_graph_optimizer.py`
  - optimization normalization

---

## 7. 为什么这条实现是“完整主线”，不是 ad hoc 修补

你明确要求：

1. 绝对不能有任何简化
2. 不能考虑 ad hoc 式的修修补补
3. 必须真实理解老板的需求，完整且正确地实现老板的所有需求

这次实现满足这三条的原因是：

### 7.1 没有走“假 detach”

没有简单地删掉 `wait()`，而是把 detach 建立在真实后台宿主上。

### 7.2 没有让 `status` 依赖脆弱的瞬时进程态

`status` 直接读 `RunStore`，所以它不是“连上某个还活着的 daemon 才能看见状态”。

### 7.3 没有回避 PR11 / PR12 过程可见性

- PR11：补了 evolution progress schema
- PR12：直接消费主线 optimization session / round 模型

没有用“先做个普通 status，PR11/PR12 以后再说”的简化路线。

### 7.4 没有把主线问题留给模型偶然行为

PR12 的 optimizer-edited child pipeline normalization 修复，就是为了避免把主线稳定性寄托在“模型正好别把 `n_run` 改坏”这种偶然条件上。

---

## 8. 本次任务总结

这次任务我是按下面的顺序完成的：

1. 先基于最新 `master` 重新建立隔离 worktree，而不是继续沿用旧的、基于 PR12 合并前状态的 worktree。
2. 将之前已经验证通过的 detached run、`status`、evolution progress 主线功能迁移到基于当前 master 的新分支。
3. 检查 master 当前已合入的 PR12 代码，补上 optimization child pipeline normalization 的健壮性修复，确保 PR12 在真实主线场景下稳定。
4. 重写本分析文档，使其明确以“PR12 已合入 master”为新基线，不再保留旧分析里的前置假设。
5. 最后基于当前分支重新执行聚焦验证，确保：
   - PR12 optimization tests 通过
   - detached run tests 通过
   - `status` 过程视图 tests 通过
   - PR11 evolution progress tests 通过

当前实现保存在：

- worktree: `/data/berabuddies/agentflow/.worktrees/async-status-masterline`
- branch: `feat/async-status-masterline`

我没有把任何内容合并回 `master`。

---

## 9. 你应该如何验证功能是正确的

下面给出一套 **可以直接复制粘贴执行** 的验证手册。

### 9.1 进入 worktree

```bash
cd /data/berabuddies/agentflow/.worktrees/async-status-masterline
```

### 9.2 自动化验证：PR12 / detach / status / PR11 progress

直接执行下面这组命令：

```bash
cd /data/berabuddies/agentflow/.worktrees/async-status-masterline

pytest tests/test_graph_optimizer.py -q

pytest tests/test_tuned_agents.py::test_run_evolution_from_payload_reports_progress -q

pytest \
  tests/test_cli.py::test_run_detach_submits_without_waiting \
  tests/test_cli.py::test_run_detach_uses_daemon_env_overrides \
  tests/test_cli.py::test_status_command_exits_for_missing_run \
  tests/test_cli.py::test_status_command_renders_summary_with_recent_events \
  tests/test_cli.py::test_status_command_supports_json_summary_output \
  tests/test_cli.py::test_status_command_shows_optimization_session \
  tests/test_cli.py::test_status_command_renders_evolution_progress \
  tests/test_cli.py::test_status_command_returns_evolution_progress_json \
  -q
```

你预期会看到：

- `tests/test_graph_optimizer.py` 全绿
- `test_run_evolution_from_payload_reports_progress` 绿
- 上面 8 个 CLI focused tests 全绿

### 9.3 手工验证：`run -d` + `status`

下面这组命令会创建一个完全本地、无外部 LLM 依赖的 demo pipeline，用 `python` utility node 来验证 detached run 和 status。

```bash
cd /data/berabuddies/agentflow/.worktrees/async-status-masterline

export AGENTFLOW_RUNS_DIR="$PWD/.tmp-agentflow-runs"
rm -rf "$AGENTFLOW_RUNS_DIR"
mkdir -p "$AGENTFLOW_RUNS_DIR"

export AGENTFLOW_DAEMON_PORT="$(python3 - <<'PY'
import socket
s = socket.socket()
s.bind(("127.0.0.1", 0))
print(s.getsockname()[1])
s.close()
PY
)"

cat > /tmp/agentflow-async-demo.json <<'EOF'
{
  "name": "async-demo",
  "working_dir": ".",
  "nodes": [
    {
      "id": "slow",
      "agent": "python",
      "prompt": "import time; time.sleep(3); print('slow done')"
    },
    {
      "id": "done",
      "agent": "python",
      "depends_on": ["slow"],
      "prompt": "print('done node')"
    }
  ]
}
EOF

RUN_ID="$(
  agentflow run /tmp/agentflow-async-demo.json -d --output json \
  | python3 -c 'import sys, json; print(json.load(sys.stdin)["id"])'
)"

echo "RUN_ID=$RUN_ID"

agentflow status "$RUN_ID" --output summary

sleep 1
agentflow status "$RUN_ID" --output json-summary

until agentflow status "$RUN_ID" --output json \
  | python3 -c 'import sys, json; d=json.load(sys.stdin); import sys as _s; print(d["status"]); _s.exit(0 if d["status"]=="completed" else 1)'
do
  sleep 1
done

agentflow status "$RUN_ID" --output summary
```

你应该能验证到：

- `run -d` 立即返回 `RUN_ID`
- `status` 在 run 完成前能看到 in-flight 状态
- 最终 run 能完成
- `status` summary 会展示进度和最近事件

### 9.4 查看当前分支提交

```bash
cd /data/berabuddies/agentflow/.worktrees/async-status-masterline
git log --oneline --decorate -8
```

你应该至少能看到这几类提交：

- detached daemon-backed run submission
- run status process view
- evolution progress in run status
- normalize optimizer-edited child pipelines

---

## 10. 最终结论

基于当前已经合并 PR12 的 `master`，老板要的需求已经可以被完整地理解为：

- **真实 detached run**
- **真实按 run_id 查询的 process-oriented status**
- **PR11 evolution 过程可见**
- **PR12 graph optimization 过程可见**

这条主线实现现在已经在 `feat/async-status-masterline` worktree 分支中完成，并且附带了可复制执行的自动化与手工验证手册，可直接用于你的 review。
