from agentflow import DAG, codex, claude

with DAG("ssh-remote-demo", working_dir=".", concurrency=2) as dag:
    remote_scan = codex(
        task_id="remote_scan",
        prompt="List the top-level files and directories in this project. Summarize the repo structure.",
        tools="read_only",
        target={
            "kind": "ssh",
            "host": "remote-server",
            "username": "deploy",
            "remote_workdir": "~/project",
        },
    )
    local_review = claude(
        task_id="local_review",
        prompt=(
            "Review the remote repo structure and suggest improvements.\n\n"
            "Remote scan:\n{{ nodes.remote_scan.output }}"
        ),
    )
    remote_scan >> local_review

print(dag.to_json())
