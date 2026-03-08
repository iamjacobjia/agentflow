from __future__ import annotations

import json
from pathlib import Path

import boto3

from agentflow.prepared import ExecutionPaths, PreparedExecution
from agentflow.runners.base import LaunchPlan, RawExecutionResult, Runner
from agentflow.specs import AwsLambdaTarget, NodeSpec


class AwsLambdaRunner(Runner):
    def _payload(self, node: NodeSpec, prepared: PreparedExecution) -> dict[str, object]:
        target = node.target
        if not isinstance(target, AwsLambdaTarget):
            raise TypeError("AwsLambdaRunner requires an AwsLambdaTarget")
        return {
            "command": prepared.command,
            "env": prepared.env,
            "cwd": target.remote_workdir,
            "stdin": prepared.stdin,
            "timeout_seconds": node.timeout_seconds,
            "runtime_files": prepared.runtime_files,
        }

    def plan_execution(
        self,
        node: NodeSpec,
        prepared: PreparedExecution,
        paths: ExecutionPaths,
    ) -> LaunchPlan:
        target = node.target
        if not isinstance(target, AwsLambdaTarget):
            raise TypeError("AwsLambdaRunner requires an AwsLambdaTarget")
        payload = self._payload(node, prepared)
        return LaunchPlan(
            kind="aws_lambda",
            env={},
            cwd=None,
            stdin=prepared.stdin,
            runtime_files=sorted(prepared.runtime_files),
            payload={
                "function_name": target.function_name,
                "region": target.region,
                "qualifier": target.qualifier,
                "invocation_type": target.invocation_type,
                "request": payload,
            },
        )

    async def execute(self, node: NodeSpec, prepared: PreparedExecution, paths: ExecutionPaths, on_output, should_cancel):
        target = node.target
        if not isinstance(target, AwsLambdaTarget):
            raise TypeError("AwsLambdaRunner requires an AwsLambdaTarget")
        if should_cancel():
            return RawExecutionResult(exit_code=130, stdout_lines=[], stderr_lines=["Cancelled before Lambda invocation"], cancelled=True)
        payload = self._payload(node, prepared)
        client = boto3.client("lambda", region_name=target.region)
        response = client.invoke(
            FunctionName=target.function_name,
            InvocationType=target.invocation_type,
            Qualifier=target.qualifier,
            Payload=json.dumps(payload).encode("utf-8"),
        )
        response_payload = json.loads(response["Payload"].read().decode("utf-8"))
        result = RawExecutionResult.model_validate(response_payload)
        for line in result.stdout_lines:
            await on_output("stdout", line)
        for line in result.stderr_lines:
            await on_output("stderr", line)
        return result
