# Optional tiered model workflow

The default toolkit still needs no model account and makes no external requests. `workflow/` adds an opt-in, serial workflow using the same memory and explicitly configured harness. The shipped provider is **fake simulation**. It is useful for learning and testing the controller, not for measuring model capability.

## Quick start

From the starter repository, run these disposable offline examples:

```sh
python3 tools/workflow_demo.py
python3 tools/workflow_demo.py --scenario escalation --output .local/escalation-demo
python3 tools/workflow_demo.py --scenario repair --lang zh-CN
python3 tools/workflow_benchmark.py
```

`--output` must name a new directory; it retains the complete project, JSON state/report, summary and command logs. The four scenarios are success, one same-tier repair, strong-tier escalation, and exhausted retries. Each uses a real failing initial test. The first three pass that same test after the simulated implementation. Expected failure is checked by the demo itself, so the full demo exits zero when all scenarios behave correctly.

After installation into your own project:

1. Configure real project commands in [harness/config.json](../../harness/config.json), following [the existing workflow](project-workflow.md). The empty scaffold deliberately cannot pass.
2. Adapt [workflow/config.json](../../workflow/config.json). For every project, list all four stages as either required in the harness or explicitly not applicable with a reason in `not_applicable`.
3. Copy/adapt [the task contract](../../workflow/tasks.example.json). Use exact relative file paths, real requirements, interfaces and acceptance stages. Keep simulation fixtures only for offline experiments.
4. Run from the installed project:

```sh
python3 workflow/run.py run --tasks workflow/tasks.example.json
python3 workflow/run.py verify --tasks workflow/tasks.example.json
python3 workflow/run.py cancel --tasks workflow/tasks.example.json
```

`--root` selects an explicit project; config/task paths are relative to it. `run` resumes the same ID. Exit 0 means accepted (or a valid `verify`/cancel request); exit 1 means a failed/blocked/cancelled run or stale acceptance; exit 2 means invalid/unavailable configuration or state. Cancellation can also use Ctrl-C or SIGTERM. A cancel request is cooperative and does not establish that an external billable call never happened.

## Controller and task contract

The controller, not a model prompt, controls the sequence:

```text
task contract → risk classification → optional architecture
→ implementation proposal → scoped patch application → deterministic checks
→ bounded repair/escalation → integrated checks → independent read-only review → report
```

A task stores `id`, `requirements`, `risk` (`low`, `standard`, `high`), `kind` (`code`, `documentation`, `mechanical`), `depends_on`, `allowed_files`, `context_files`, `interfaces`, `acceptance`, and a task `budget`. The run stores `run_id`, optional expected `base_revision`, observed base revision/content hash, deadlines, attempts, state transitions, exact stage model configuration, call ledger, patches and evidence. A null expected revision accepts the inspected checkout and records its actual revision; it does not pretend a clean Git commit exists.

Dependencies are topologically validated before calls. Missing references, duplicate IDs and cycles fail. A failed dependency blocks downstream implementation or final acceptance. Tasks execute serially; successful provisional checks allow a dependent implementation to proceed, but only final integrated checks and independent review establish success.

Explicit high risk is never downgraded. A conservative keyword/path/interface check raises sensitive work such as authorization, payments, migrations or deployment to high risk. This heuristic is a minimum, not a security classifier: the operator must declare additional risk. Low-risk tasks skip architecture. Normal coding uses the implementer role; low-risk documentation/mechanical tasks use `fast_tier`. High-risk work goes directly to `strong_tier`. Architecture is advisory text and cannot create tasks, widen file scope or change executable controls. The architect does not observe every tool call.

Statuses are `pending`, `running`, `awaiting_verification`, `repairing`, `escalating`, `success`, `failed`, `blocked`, and `cancelled`. Call outcomes additionally include `uncertain`. A rejected review or boundary violation fails; unavailable dependencies, ambiguous requirements, exhausted retries and budgets block. Default recovery is one same-tier repair and one strong-tier attempt after the initial implementation, then blocked. Limits are configurable.

## Model and resource configuration

Three roles (`architect`, `implementer`, `reviewer`) map to logical tiers. Each tier specifies:

- `provider` and an exact `model` registered in that provider's `models` allowlist;
- optional supported `effort` (otherwise null);
- `max_input_tokens`, `max_output_tokens`, `timeout_seconds`;
- `reliable_usage` and `price_per_million: {"input": ..., "output": ...}` or null.

Provider kinds are `fake` and `cli`; unknown kinds or unregistered model IDs fail before execution. Registration is an operator assertion, not live discovery of account entitlements. Display names such as “Opus 5.5”, “Astra 6”, “Sonnet”, “Haiku” or “6.1 Sol” are not preconfigured API IDs. Verify the installed bridge's supported model IDs, effort values, access and current rates before enabling it. No combination is assumed optimal.

Every run and task has `calls`, `tokens`, `seconds`, and `usd` limits. USD may be null only outside strict-money mode. Zero USD is valid for the free fake adapter. All architect, implementation, failed, repaired, escalated and reviewer calls count. The controller reserves maximum input/output tokens and configured maximum cost **before** launching a call, then reconciles with returned usage. Unknown usage retains the maximum token/cost reservation and is reported as `unknown`, never as zero. A missing price makes cost unknown. Reported estimates are not provider invoices; price correctness, overhead, caching and server billing remain the operator/bridge's responsibility.

Strict-money mode rejects real calls without reliable declared metering and finite price bounds. Unknown usage returned under strict mode blocks further work. Non-strict mode permits unknown costs and treats a money cap as advisory when it cannot be measured; call/token/time caps still apply. A bridge must enforce the requested model limits and perform exactly one billable request per protocol call, with no hidden retries or autonomous subcalls. This controller cannot enforce a provider's invoice against a bridge that violates that contract.

The controller reserves calls/tokens/money for each unfinished task's final reviewer and reserves wall time for final checks and review. `seconds` is elapsed wall time including checks, failed attempts and downtime between resumes. Time reserved for review uses the configured reviewer timeout. UTF-8 request size provides a conservative context bound; it is not a tokenizer or a usage estimate. Bridges must also enforce their own tokenizer's input/output limits. Oversized context blocks instead of silently truncating requirements or diff.

Checks only trigger model repair for **explicitly classified code failures**. For example, the offline fixture registers `check_failure_categories: {"app/test": {"1": "code"}}` because that command is a pure assertion test. Unmapped nonzero exits are infrastructure failures. Available categories are `code`, `infrastructure`, `dependency`, and `ambiguity`. Do not classify an installer/network wrapper's generic exit code as code. Missing executables, timeouts and cancelled processes never trigger a more expensive model. No dependency installation is automatic.

## Real CLI integration: protocol version 1

`CliAdapter` is implemented: it starts the configured absolute executable with argv (no shell), sends one JSON object on stdin, receives one JSON object on stdout, validates protocol/usage, handles process failure/timeouts/cancellation and records uncertainty. It is a protocol adapter for an installed bridge, not a claim that arbitrary coding CLIs already speak this protocol. Contract tests execute real local mock bridge processes. **No vendor service integration, real credential or paid model call was used to validate this MVP.**

Configure a `cli` provider with `argv`, exact supported `models`, and optional `env_allowlist`. Example shape (replace all placeholders with locally verified values; this is not a runnable vendor preset):

```json
{
  "kind": "cli",
  "argv": ["/absolute/path/to/your-agent-bridge", "--json-stdio"],
  "models": ["EXACT_SUPPORTED_MODEL_ID"],
  "env_allowlist": ["MY_MODEL_API_KEY"]
}
```

Use the native absolute executable path on Windows. Prefer an actual executable/interpreter, not a shell/batch wrapper. Put credential **names**, never values, in configuration. The adapter inherits only basic runtime variables plus explicit allowlisted names. It does not load `.env`, user shell profiles or credentials itself. The bridge runs in a disposable working directory and receives only bounded explicit files/context, memory brief, requirements, interfaces, existing plan, dependency states, feedback, real check evidence, actual before/after diff, acceptance rules and content/configuration hashes. It must return a proposal rather than editing the repository.

Request fields include `protocol_version: 1`, stable `call_id`, `role`, `mode` (`propose_changes` or `read_only`), `model`, `effort`, limits, `task`, `files` (text and SHA-256), `changes`, `evidence`, and the context above. Preserve `call_id` for provider-side reconciliation. Responses:

```json
{
  "protocol_version": 1,
  "changes": [{"path": "app.py", "before": "SHA256_OF_REQUEST_FILE", "content": "full replacement text"}],
  "usage": {"input_tokens": 120, "output_tokens": 80}
}
```

`before` is null only for a new file. `changes` is required for implementers; an empty list proposes no change. Deletion is not supported. Architects return `plan` and optional `ambiguities: []`. Reviewers return `verdict: "approve" | "reject"` and `approved_rule_changes: ["exact/path"]`; they cannot return changes. An error response has `error: {"category": "infrastructure" | "dependency" | "code" | "ambiguity"}` and usage when known. Unknown usage is JSON null. Durations are measured by the controller. Responses are bounded to 1 MiB; do not write progress text to stdout.

A nonzero CLI exit, malformed response, timeout or cancellation after launch has an uncertain outcome: no blind resend. Raw CLI stderr is not stored because it may contain credentials. Responses containing injected allowlisted environment values are rejected; check logs redact those known values. This is not general secret detection. Review source/context and use a clean environment without production credentials.

Only after explicit external-call authorization:

```sh
python3 workflow/run.py run --config workflow/config.json --tasks workflow/tasks.example.json --allow-real
```

The flag authorizes the configured CLI in that invocation; it does not install anything or establish provider access. There is no automatic account creation, payment, publishing or deployment.

## Acceptance and safety boundaries

All required lint/typecheck/test/build commands and memory validation run as real subprocesses. Evidence stores argv, relative cwd, exit code, duration, log path/hash, tested content hash and acceptance-configuration hash. Model claims of passing tests are ignored. The independent reviewer gets real diff/evidence and cannot overrule a required failure. It is a distinct role/call with read-only output, not necessarily a different vendor or guaranteed unbiased judge.

Model patches use exact allowlisted files and preimage hashes. Absolute paths, traversal, symlinks, ignored runtime paths, duplicate patch paths and out-of-scope changes fail. Harness/workflow/CI controls and project instructions cannot be edited by a model run. Recognized test/rule files, including directly invoked check scripts, require explicit `allow_rule_changes` and independent reviewer approval. There is no delete operation. Less obvious indirect test inputs must be identified in your allowed scope/rule policy; code review still matters. Treat standards changes as a separate reviewed task when controls must change.

Final acceptance binds the integrated tree's content/executable-bit hash and acceptance configuration, rather than trusting a model-reported revision. Git HEAD can remain unchanged for an uncommitted patch, so both revision and hash are reported. Later source/test/config changes invalidate `verify`. Source-only changes may be rechecked/reviewed on resume without replaying an old patch. Changed config/contracts/harness require a new run ID. Tests may write disposable outputs into `.local/`; persistent changes elsewhere during checks fail. `.git`, `.local`, `__pycache__`, and `.pyc` are outside the content hash and must never be application/test source authorities.

One writer lock covers the entire workflow working tree. Use a trusted working directory with no concurrent writers. This code and Git worktrees are **not OS sandboxes**: an arbitrary configured CLI or check executable still has the user's OS permissions. Direct CLI edits are detected by tree comparison, not prevented or automatically reverted. POSIX execution kills the process group on completion/timeout/cancel; Windows timeout/cancel uses `taskkill /T /F`. Detached/new-session workers and Windows children surviving an already-exited parent need external containment. Filesystem checks do not defeat hostile races or arbitrary same-user state tampering. Use containers/OS isolation for untrusted tools; never supply production credentials.

## Recovery, reports and troubleshooting

State lives at `.local/workflow/<run_id>/state.json`; `report.json`, `summary.txt` and `check-*.log` provide the handoff. Call reservations and responses are saved atomically, and completed responses for all roles are reused. Patch journals accept either the preimage or the already-applied postimage after interruption. Completed runs do not repeat calls, charges, patches or checks. In-flight interrupted calls become `uncertain`, retain their reservation and block; reconcile with the external provider before explicitly starting any new run. No automated retry/resolution of uncertain billing is provided.

A hard kill can leave `.local/workflow/lock`. Confirm the former process and its children have stopped before removing **only that lock** and resuming. Never delete state to conceal an uncertain call. A cancellation marker remains in the run directory; use a new run ID after reconciling cancelled work. Report generation itself does not make stale acceptance valid; use `verify` against the current checkout.

Common blocked reasons: `budget_exhausted` (increase a reviewed limit/new run), `deadline`, `context_limit` (split the task/context), `dependency` (fix memory/required resources), `infrastructure` (inspect command logs), `ambiguity` (clarify the contract), `patch_conflict` (inspect concurrent/manual edits), `retry_exhausted`, `unknown_usage`, and `uncertain_call`. Terminal failed/blocked tasks do not automatically restart. Reports distinguish estimates, reservations, unknown usage and simulation, and include the baseline/final revision and hashes, stage configuration, attempts, time, coverage and evidence.

## Comparison and scope

`tools/workflow_benchmark.py` compares all-strong, single-practical and tiered strategies against identical fixed tasks and acceptance rules. Its default is an **offline simulation with artificial rates and scripted outcomes**. Local elapsed time is controller/check overhead, not service latency. It cannot demonstrate model quality, savings or an optimal choice.

For future authorized experiments, the importer accepts repeated `--report STRATEGY=path/to/report.json`. It rejects differing task/source/check fingerprints and mixed simulated/real reports. Metrics include final success rate, total cost divided by final successful tasks (including failures, architecture, repairs and reviews), elapsed time, rework and tier-upgrade rate. Unknown costs stay unknown. Human fixture/rule parity must still be reviewed; fingerprints are not an external audit.

Implemented: serial dependency scheduling, bounded roles, fake and JSON CLI adapters, persistent accounting/recovery, deterministic checks, final review and comparison reports. Planned, not implemented: parallel implementers, service-specific presets, automatic uncertain-call reconciliation, semantic retrieval and learned routing. No combination guarantees correctness, speed or best cost.
