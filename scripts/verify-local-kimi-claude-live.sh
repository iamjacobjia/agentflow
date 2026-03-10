#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
. "$script_dir/custom-local-kimi-helpers.sh"

python_bin="$(agentflow_repo_python "$repo_root")"
tmpdir="$(mktemp -d)"
stdout_path="$tmpdir/claude-live.stdout"
stderr_path="$tmpdir/claude-live.stderr"

cleanup() {
  local exit_code=$?
  trap - EXIT
  if [ "$exit_code" -eq 0 ]; then
    rm -rf "$tmpdir"
    return
  fi

  printf "claude live probe failed in the Kimi-backed bash login shell.\n" >&2

  if [ -f "$stdout_path" ] && [ -s "$stdout_path" ]; then
    printf "\nclaude live probe stdout:\n" >&2
    sed -n '1,80p' "$stdout_path" >&2
  fi

  if [ -f "$stderr_path" ] && [ -s "$stderr_path" ]; then
    local filtered_stderr
    filtered_stderr="$(
      grep -v \
        -e '^bash: cannot set terminal process group (' \
        -e '^bash: initialize_job_control: no job control in background:' \
        -e '^bash: no job control in this shell$' \
        "$stderr_path" || true
    )"
    if [ -n "$filtered_stderr" ]; then
      printf "\nclaude live probe stderr:\n" >&2
      printf "%s\n" "$filtered_stderr" >&2
    fi
  fi

  printf "\nkept tempdir for debugging: %s\n" "$tmpdir" >&2
}

trap cleanup EXIT

(
  cd "$repo_root"
  agentflow_run_with_timeout "$python_bin" bash -lic '
set -euo pipefail
command -v kimi >/dev/null 2>&1
kimi >/dev/null
claude -p "Reply with exactly: claude ok" \
  --output-format text \
  --permission-mode bypassPermissions \
  --tools "" \
  --no-session-persistence
' >"$stdout_path" 2>"$stderr_path"
)

probe_output="$(
  awk 'NF { last = $0 } END { print last }' "$stdout_path"
)"
if [ "$probe_output" != "claude ok" ]; then
  printf "claude live probe returned unexpected output: %s\n" "$probe_output" >&2
  exit 1
fi

printf "claude live probe: ok - %s\n" "$probe_output"
