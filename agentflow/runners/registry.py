from __future__ import annotations

from agentflow.runners.aws_lambda import AwsLambdaRunner
from agentflow.runners.base import Runner
from agentflow.runners.container import ContainerRunner
from agentflow.runners.local import LocalRunner
from agentflow.runners.ssh import SSHRunner


class RunnerRegistry:
    def __init__(self) -> None:
        self._registry: dict[str, Runner] = {
            "local": LocalRunner(),
            "container": ContainerRunner(),
            "aws_lambda": AwsLambdaRunner(),
            "ssh": SSHRunner(),
        }

    def register(self, kind: str, runner: Runner) -> None:
        self._registry[kind] = runner

    def get(self, kind: str) -> Runner:
        return self._registry[kind]


default_runner_registry = RunnerRegistry()
