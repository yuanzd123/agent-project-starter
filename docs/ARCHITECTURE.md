# Architecture

[简体中文](ARCHITECTURE.zh-CN.md) · [Workflow guide](WORKFLOW.md)

The project has two independent entry points: a standalone prompt and an executable scaffold. Either can be used without the other.

## Components

- `tools/bootstrap.py` overlays language-specific content onto `template/`, plans changes, checks ordinary conflicts and symlink boundaries, and creates missing files. It does not install software or alter Git configuration.
- `template/harness/run.py` validates explicit project configuration and runs argument arrays in the registered working directory. It stops on the first failure. A whole-project `check` also validates memory.
- `template/scripts/memory.py` validates registry structure, generates the index, and retrieves active lessons using tags, status, review dates, limits, and a character budget.
- `template/workflow/` is an optional serial controller with validated task dependencies, risk routing, persisted call/patch journals, budgets, fake and JSON CLI adapters, final integrated checks and independent read-only review. It imports the harness configuration validator and reuses memory briefs.
- `tools/workflow_demo.py` and `tools/workflow_benchmark.py` exercise offline execution and report comparison.
- `tools/demo.py` assembles a temporary project and exercises both passing and failing paths without external services.
- `tools/check_locales.py` assembles each locale and checks lifecycle parity and the final memory structure.
- `tools/check_docs.py` checks repository-local documentation destinations.

## Explicit boundaries

The harness does not infer and run commands from every directory. The bootstrap prompt asks the agent to inspect manifests and propose real configuration first. Configured commands remain trusted executable input, and the runner does not sandbox them.

The index is a generated view, not a second source of lesson truth. LATEST owns current project status; lesson bodies explain reusable causes and actions. State metadata lives in the registry. Private agent caches are not another project authority.

English is the base template. A locale replaces human-readable files at the same relative paths, while runtime scripts and the starter license come from the base. CI validates both assembled outputs.

## Design choices

| Choice | Reason | Reconsider when |
| --- | --- | --- |
| Python standard library | Small install surface, readable behavior | A dependency removes enough complexity to justify itself |
| Markdown + JSON | Reviewable, portable, no service needed | Structured queries become a demonstrated need |
| Explicit tags | Predictable retrieval and low overhead | Real misses justify a better retrieval method |
| No automatic uploads | Project data and publishing permissions remain explicit | A separate opt-in workflow defines its boundaries |
| Optional serial orchestration | Keep the lightweight entry; bounded dependencies need no parallel framework | Measured workload justifies parallel implementation |
| Conflict-first bootstrap | Protect existing project content | A reviewed migration format can preserve user changes |

## Verification evidence

The regression suite checks behavior rather than only file presence: failure propagation, preflight validation, timeouts, command working directories, retrieval exclusions, replacement cycles, conflicts, idempotence and language assembly. The CI badge links to actual runs; the presence of a workflow file alone is not a passing result.

## Optional execution decisions

Roles map to operator-registered tiers, not hardcoded commercial model names. The CLI adapter uses an explicit local JSON protocol so runtime remains standard-library-only. Vendor-specific SDKs/presets and paid service validation are outside this MVP. Simulation is labelled in every report.

One working-tree lock protects serial runs. Before each external boundary the call key and resource reservation are persisted; responses for all roles are reused on recovery. Interrupted in-flight calls remain uncertain. Patch journals persist preimages and diffs before atomic replacements. These are crash-recovery mechanisms, not a security sandbox or a distributed transaction.

Checks execute trusted argv arrays with explicit cwd/timeouts. Only explicitly classified code failures permit bounded repair/escalation; infrastructure, dependencies and ambiguous requirements block. All tasks receive integrated final checks and read-only review against the final content/config hash. Review cannot override a failed check. Config/harness changes require a new run, while stale source acceptance must be reverified. Rules changes need explicit scope and independent approval.

Runtime evidence belongs in ignored `.local/`. No state, credentials, model costs, service access, absolute project paths or private history are imported into shared lesson memory automatically. The existing bootstrap remains conflict-first and installs identical runtime code for both languages.
