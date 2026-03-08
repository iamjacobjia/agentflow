from agentflow.defaults import default_smoke_pipeline_path
from agentflow.loader import load_pipeline_from_path


def test_bundled_smoke_pipeline_runs_both_agents_in_shared_kimi_bootstrap():
    pipeline = load_pipeline_from_path(default_smoke_pipeline_path())
    codex_node = next(node for node in pipeline.nodes if node.id == "codex_plan")
    claude_node = next(node for node in pipeline.nodes if node.id == "claude_review")

    assert pipeline.concurrency == 2
    assert codex_node.target.kind == "local"
    assert codex_node.target.shell == "bash"
    assert codex_node.target.shell_login is True
    assert codex_node.target.shell_interactive is True
    assert codex_node.target.shell_init == ["command -v kimi >/dev/null 2>&1", "kimi"]
    assert codex_node.depends_on == []
    assert claude_node.target.shell_init == ["command -v kimi >/dev/null 2>&1", "kimi"]
    assert claude_node.depends_on == []
