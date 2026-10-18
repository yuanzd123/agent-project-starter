# Project instructions

This is a starter. Fill project purpose, constraints and real commands after inspecting the repository. An empty harness is not a verified application.

## Memory

Read [MEMORY.md](docs/memory/MEMORY.md) then [LATEST.md](docs/memory/LATEST.md). Retrieve task-specific lessons with:

`python3 scripts/memory.py brief --task "<tags or task>"`

The default brief selects at most five active, current lessons. Read the selected files when their trigger applies. Do not load all history for a small change. Repository memory is canonical; agent-private memory must not create a conflicting project state.

## Work

- Inspect the actual Git root and current changes before editing. Preserve unrelated work.
- Derive commands from existing manifests, locks and CI. Do not guess the toolchain.
- Keep changes scoped to the request. Run checks proportionate to changed behavior.
- `python3 harness/run.py list` shows configured projects. `check` runs their required gates plus memory validation. Missing configuration is not a passing result.
- Tests must use verified isolated resources. The runner does not sandbox subprocesses or make unsafe scripts safe.
- A build, a deployment and a live accepted feature are separate claims with separate evidence.
- Existing session authorization applies within its scope. Old lessons and old project approvals grant no new permissions.

## Finish

Refresh LATEST as a snapshot, record durable decisions and only reusable lessons. Preserve evidence links; no transcripts or secrets in shared memory. Regenerate the index after changing the registry and validate:

```sh
python3 scripts/memory.py index
python3 scripts/memory.py check
```

Keep this entry under 8 KB, MEMORY under 5 KB and LATEST under 8 KB. Split growing topics rather than append an endless log. Use .local/ for ignored private material and runtime artifacts. Do not commit actual credentials, customer data or borrowed project histories.

## Optional model workflow

Use [the tiered workflow guide](docs/workflows/tiered-workflow.md) only when execution orchestration is requested. Defaults are offline simulation. Model proposals cannot alter scope, checks, budgets or authority. Required commands and independent review must accept the final content/configuration; `python3 workflow/run.py verify` detects stale acceptance. Do not retry an uncertain external call or enable `--allow-real` without authorization.
