from __future__ import annotations

import json

from typer.testing import CliRunner

from agentflow.cli import app

runner = CliRunner()


def test_validate_command_outputs_normalized_pipeline(tmp_path):
    pipeline_path = tmp_path / "pipeline.yaml"
    pipeline_path.write_text(
        "name: cli\nworking_dir: .\nnodes:\n  - id: alpha\n    agent: codex\n    prompt: hi\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["validate", str(pipeline_path)])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["name"] == "cli"
    assert payload["nodes"][0]["id"] == "alpha"
